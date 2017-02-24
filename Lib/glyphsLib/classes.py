#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2016 Georg Seifert. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re, traceback

from casting import num, transform, point, glyphs_datetime, color, CUSTOM_INT_PARAMS, CUSTOM_FLOAT_PARAMS, CUSTOM_TRUTHY_PARAMS, CUSTOM_INTLIST_PARAMS, floatToString, truthy
import collections

__all__ = [
	"GSFont", "GSCustomParameter", "GSInstance", 
]

def hint_target(line = None):
	if line is None:
		return None
	if line[0] == "{":
		return point(line)
	else:
		return line

def isString(string):
	return isinstance(string, (str, unicode))

class GSBase(object):
	_classesForName = {}
	_wrapperKeysTranslate = {}
	def __init__(self):
		for key in self._classesForName.keys():
			try:
				dict_type = self._classesForName[key]
				if issubclass(dict_type, GSBase):
					value = []
				else:
					value = None
				setattr(self, key, value)
			except:
				pass
	
	def __repr__(self):
		content = ""
		if hasattr(self, "_dict"):
			content = str(self._dict)
		return "<%s %s>" % (self.__class__.__name__, content)
	
	def classForName(self, name):
		return self._classesForName.get(name, str)
	
	def __contains__(self, key):
		return hasattr(self, key) and getattr(self, key) is not None
	
	def __setitem__(self, key, value):
		try:
			if type(value) is str and key in self._classesForName:
				new_type = self._classesForName[key]
				if new_type is unicode:
					value = value.decode('utf-8')
				else:
					try:
						value = new_type().read(value)
					except:
						value = new_type(value)
			key = self._wrapperKeysTranslate.get(key, key)
			setattr(self, key, value)
		except:
			print traceback.format_exc()

class Proxy(object):
	def __init__(self, owner):
		self._owner = owner
	def __repr__(self):
		"""Return list-lookalike of representation string of objects"""
		strings = []
		for currItem in self:
			strings.append("%s" % (currItem))
		return "(%s)" % (', '.join(strings))
	def __len__(self):
		Values = self.values()
		if Values is not None:
			return len(Values)
		return 0
	def pop(self, i):
		if type(i) == int:
			node = self[i]
			del self[i]
			return node
		else:
			raise(KeyError)
	def __iter__(self):
		Values = self.values()
		if Values is not None:
			for element in Values:
				yield element
	def index(self, Value):
		return self.values().index(Value)
	def __copy__(self):
		return list(self)
	def __deepcopy__(self, memo):
		return [x.copy() for x in self.values()]

	def setter(self, values):
		method = self.setterMethod()
		if type(values) == list:
			method(values)
		elif type(values) == tuple or values.__class__.__name__ == "__NSArrayM" or type(values) == type(self):
			method(list(values))
		elif values is None:
			method(list())
		else:
			raise TypeError

class LayersIterator:
	def __init__(self, owner):
		self.curInd = 0
		self._owner = owner
	def __iter__(self):
		return self
	def next(self):
		if self._owner.parent:
			if self.curInd < len(self._owner.parent.masters):
				FontMaster = self._owner.parent.masters[self.curInd]
				Item = self._owner._layers.get(FontMaster.id, None)
			else:
				if self.curInd >= len(self._owner.layers):
					raise StopIteration
				ExtraLayerIndex = self.curInd - len(self._owner.parent.masters)
				Index = 0
				ExtraLayer = None
				while ExtraLayerIndex >= 0:
					ExtraLayer = self._owner.pyobjc_instanceMethods.layers().objectAtIndex_(Index)
					if ExtraLayer.layerId != ExtraLayer.associatedMasterId:
						ExtraLayerIndex = ExtraLayerIndex - 1
					Index = Index + 1
				Item = ExtraLayer
			self.curInd += 1
			return Item
		else:
			if self.curInd >= self._owner.countOfLayers():
				raise StopIteration
			Item = self._owner.pyobjc_instanceMethods.layers().objectAtIndex_(self.curInd)
			self.curInd += 1
			return Item
		return None

class GlyphLayerProxy (Proxy):
	def __getitem__(self, Key):
		if type(Key) == slice:
			return self.values().__getitem__(Key)
		if type(Key) is int:
			if Key < 0:
				Key = self.__len__() + Key
			if self._owner.parent:
				masterCount = len(self._owner.parent.masters)
				if Key < masterCount:
					FontMaster = self._owner.parent.masters[Key]
					return self._owner._layers.get(FontMaster.id, None)
				else:
					ExtraLayerIndex = Key - masterCount
					Index = 0
					ExtraLayer = None
					while ExtraLayerIndex >= 0:
						ExtraLayer = self._owner._layers[Index]
						if ExtraLayer.layerId != ExtraLayer.associatedMasterId:
							ExtraLayerIndex = ExtraLayerIndex - 1
						Index = Index + 1
					return ExtraLayer
		return self._owner._layers.get(Key, None)
	
	def __setitem__(self, key, layer):
		if type(key) is int and self._owner.parent:
			if key < 0:
				key = self.__len__() + key
			master = self._owner.parent.masters[key]
			key = FontMaster.id
		self._owner._setupLayer(layer, key)
		self._owner._layers[key] = layer
	
	def __delitem__(self, key):
		if type(key) is int and self._owner.parent:
			if key < 0:
				key = self.__len__() + key
			Layer = self.__getitem__(key)
			key = Layer.layerId
		del(self._owner._layers[key])
	def __iter__(self):
		return LayersIterator(self._owner)
	def __len__(self):
		return len(self._owner._layers)
	def values(self):
		return self._owner._layers.values()
	def append(self, Layer):
		if not Layer.associatedMasterId:
			Layer.associatedMasterId = self._owner.parent.masters[0].id
		self._owner.setLayerForKey(Layer, uuid4())
	def extend(self, Layers):
		for Layer in Layers:
			self.append(Layer)
	def remove(self, Layer):
		return self._owner.removeLayerForKey_(Layer.layerId)
	def insert(self, Index, Layer):
		self.append(Layer)
	def setter(self, values):
		newLayers = {}
		if type(values) == list or type(values) == tuple or type(values) == type(self):
			for layer in values:
				newLayers[layer.layerId] = layer
		elif type(values) == dict: # or isinstance(values, NSDictionary)
			for (key, layer) in values.items() :
				newLayers[layer.layerId] = layer
		else:
			raise TypeError
		for (key, layer) in newLayers.items():
			self._owner._setupLayer(layer, key)
		self._owner._layers = newLayers

class CustomParametersProxy(Proxy):
	def __getitem__(self, key):
		if type(key) == slice:
			return self.values().__getitem__(key)
		if type(key) is int:
			return self._owner._customParameters[key]
		else:
			for customParameter in self._owner._customParameters:
				if customParameter.name == key:
					return customParameter
		return None
	
	def __setitem__(self, key, value):
		Value = self._owner.__getitem__(key)
		if Value is not None:
			Value.value = value
		else:
			parameter = GSCustomParameter(key, value)
			self._owner._customParameters.append(parameter)
	def __delitem__(self, key):
		parameter = self.__getitem__(key)
		if parameter is not None:
			self._owner._customParameters.remove(parameter)
		else:
			raise KeyError
	def __contains__(self, item):
		if isString(item):
			return self._owner.__getitem__(item) != None
		return item in self._owner._customParameters
	def __iter__(self):
		for index in range(len(self._owner._customParameters)):
			yield self._owner._customParameters[index]
	def append(self, parameter):
		parameter.parent = self._owner
		self._owner._customParameters.append(parameter)
	def extend(self, parameters):
		for parameter in parameters:
			parameter.parent = self._owner
			self._owner._customParameters.append(parameter)
	def remove(self, parameter):
		if isString(parameter):
			parameter = self.__getitem__(parameter)
		self._owner._customParameters.remove(parameter)
	def insert(self, index, parameter):
		parameter.parent = self._owner
		self._owner._customParameters.insert(index, parameter)
	def __len__(self):
		return len(self._owner._customParameters)
	def values(self):
		return self._owner._customParameters
	def __setter__(self, parameters):
		for parameter in parameters:
			parameter.parent = self._owner
		self._owner._customParameters = parameters
	def setterMethod(self):
		return self.__setter__

class GSCustomParameter(GSBase):
	_classesForName = {
		"name": str,
		"value": str,  # TODO: check 'name' to determine proper class
	}
	
	def __repr__(self):
		return "<%s %s: %s>" % (self.__class__.__name__, self.name, self._value)
	
	def getValue(self):
		return self._value
	
	def setValue(self, value):
		"""Cast some known data in custom parameters."""
		if self.name in CUSTOM_INT_PARAMS:
			value = int(value)
		if self.name in CUSTOM_FLOAT_PARAMS:
			value = float(value)
		if self.name in CUSTOM_TRUTHY_PARAMS:
			value = truthy(value)
		if self.name in CUSTOM_INTLIST_PARAMS:
			value = intlist(value)
		elif self.name == 'DisableAllAutomaticBehaviour':
			value = truthy(value)
		self._value = value
	
	value = property(getValue, setValue)


class GSAlignmentZone(GSBase):
	def __init__(self, line = None):
		if line is not None:
			p = point(line)
			self.position = float(p.value[0].value)
			self.size = float(p.value[1].value)
	
	def __repr__(self):
		return "<%s pos:%g size:%g>" % (self.__class__.__name__, self.position, self.size)
	
	def plistValue(self):
		return "\"{%s, %s}\"" % (floatToString(self.position), floatToString(self.size))

class GSGuideLine(GSBase):
	_classesForName = {
		"alignment": str,
		"angle": float,
		"locked": truthy,
		"position": point,
		"showMeasurement": truthy,
	}


class GSFontMaster(GSBase):
	_classesForName = {
		"alignmentZones": GSAlignmentZone,
		"ascender": float,
		"capHeight": float,
		"custom": str,
		"customParameters": GSCustomParameter,
		"customValue": float,
		"descender": float,
		"guideLines": GSGuideLine,
		"horizontalStems": int,
		"id": str,
		"italicAngle": float,
		"userData": dict,
		"verticalStems": int,
		"visible": truthy,
		"weight": str,
		"weightValue": float,
		"width": str,
		"widthValue": float,
		"xHeight": float,
	}
	def __init__(self):
		super(GSFontMaster, self).__init__()
		self._name = None
		self._customParameters = []
		self._weight = "Regular"
		self._width = "Regular"
		self._custom = None
		self._custom1 = None
		self._custom2 = None
		self.italicAngle = 0
		self.widthValue = 100
		self.weightValue = 100
	
	def __repr__(self):
		return "<GSFontMaster \"%s\" width %s weight %s>" % (self.name, self.widthValue, self.weightValue)
	
	@property
	def name(self):
		if self._name is not None:
			return self._name
		name = self.customParameters["Master Name"]
		if name is None:
			names = [self._weight, self._width]
			if self._custom and len(self._custom) and self._custom not in names:
				names.append(self._custom)
			if self._custom1 and len(self._custom1) and self._custom1 not in names:
				names.append(self._custom1)
			if self._custom2 and len(self._custom2) and self._custom2 not in names:
				names.append(self._custom2)
			
			if len(names) > 1:
				names.remove("Regular")
			
			if abs(self.italicAngle) > 0.01:
				names.add("Italic")
			name = " ".join(list(names))
		self._name = name
		return name
		
	customParameters = property(lambda self: CustomParametersProxy(self),
								lambda self, value: CustomParametersProxy(self).setter(value))

class GSNode(GSBase):
	
	def __init__(self, line = None):
		if line is not None:
			rx = '([-.e\d]+) ([-.e\d]+) (LINE|CURVE|OFFCURVE|n/a)(?: (SMOOTH))?'
			m = re.match(rx, line).groups()
			self.position = (float(m[0]), float(m[1]))
			self.type = m[2].lower()
			self.smooth = bool(m[3])
		else:
			self.position = (0, 0)
			self.type = 'line'
			self.smooth = False
	
	def __repr__(self):
		content = self.type
		if self.smooth:
			content += " smooth"
		return "<%s %g %g %s>" % (self.__class__.__name__, self.position[0], self.position[1], content)
	
	def plistValue(self):
		content = self.type.upper()
		if self.smooth:
			content += " SMOOTH"
		return "\"%s %s %s\"" % (floatToString(self.position[0]), floatToString(self.position[1]), content)

class GSPath(GSBase):
	_classesForName = {
		"nodes": GSNode,
		"closed": truthy
	}


class GSComponent(GSBase):
	_classesForName = {
		"alignment": int,
		"anchor": str,
		"locked": truthy,
		"name": str,
		"piece": dict,
		"transform": transform,
	}
	

class GSAnchor(GSBase):
	_classesForName = {
		"name": str,
		"position": point,
	}


class GSHint(GSBase):
	_classesForName = {
		"horizontal": truthy,
		"options": int, # bitfield
		"origin": point, # Index path to node
		"other1": point, # Index path to node for third node
		"other2": point, # Index path to node for fourth node
		"place": point, # (position, width)
		"scale": point, # for corners
		"stem": int, # index of stem
		"target": hint_target,  # Index path to node or 'up'/'down'
		"type": str,
	}


class GSFeature(GSBase):
	_classesForName = {
		"automatic": truthy,
		"code": unicode,
		"name": str,
		"notes": unicode,
	}
	def getCode(self):
		return self._code
		
	def setCode(self, code):
		replacements = (
			('\\012', '\n'), ('\\011', '\t'), ('\\U2018', "'"), ('\\U2019', "'"),
			('\\U201C', '"'), ('\\U201D', '"'))
		for escaped, unescaped in replacements:
			code = code.replace(escaped, unescaped)
		self._code = code
	code = property(getCode, setCode)

class GSClass(GSFeature):
	_classesForName = {
		"automatic": truthy,
		"code": unicode,
		"name": str,
		"notes": unicode,
	}


class GSAnnotation(GSBase):
	_classesForName = {
		"angle": float,
		"position": point,
		"text": str,
		"type": str,
		"width": float, # the width of the text field or size of the cicle
	}


class GSInstance(GSBase):
	_classesForName = {
		"customParameters": GSCustomParameter,
		"exports": truthy,
		"instanceInterpolations": dict,
		"interpolationCustom": float,
		"interpolationWeight": float,
		"interpolationWidth": float,
		"isBold": truthy,
		"isItalic": truthy,
		"linkStyle": str,
		"manualInterpolation": truthy,
		"name": str,
		"weightClass": str,
		"widthClass": str,
	}
	def interpolateFont():
		pass
	
	def __init__(self):
		self.exports = True
		self.name = "Regular"
		self.name = "Regular"
		self.linkStyle = ""
		self.interpolationWeight = 100
		self.interpolationWidth = 100
		self.interpolationCustom = 0
		self.visible = True
		self.isBold = False
		self.isItalic = False
		self.widthClass = "Medium (normal)"
		self.weightClass = "Regular"
	
	customParameters = property(lambda self: CustomParametersProxy(self),
								lambda self, value: CustomParametersProxy(self).setter(value))


class GSBackgroundLayer(GSBase):
	_classesForName = {
		"anchors": GSAnchor,
		"annotations": GSAnnotation,
		"backgroundImage": dict, # TODO
		"components": GSComponent,
		"guideLines": GSGuideLine,
		"hints": GSHint,
		"paths": GSPath,
		"visible": truthy,
	}


class GSLayer(GSBase):
	_classesForName = {
		"anchors": GSAnchor,
		"annotations": GSAnnotation,
		"associatedMasterId": str,
		"background": GSBackgroundLayer, 
		"backgroundImage": dict, # TODO
		"color": color,
		"components": GSComponent,
		"guideLines": GSGuideLine,
		"hints": GSHint,
		"layerId": str,
		"leftMetricsKey": str,
		"name": unicode,
		"paths": GSPath,
		"rightMetricsKey": str,
		"userData": dict,
		"vertWidth": float,
		"visible": truthy,
		"width": float,
		"widthMetricsKey": str,
	}
	def __repr__(self):
		name = self.name
		try:
			#assert self.name
			name = self.name
		except:
			name = 'orphan (n)'
		try:
			assert self.parent.name
			parent = self.parent.name
		except:
			parent = 'orphan'
		return "<%s \"%s\" (%s)>" % (self.__class__.__name__, name, parent)
	@property
	def name(self):
		if self.associatedMasterId and self.associatedMasterId == self.layerId and self.parent:
			master = self.parent.parent.masterForId(self.associatedMasterId)
			if master:
				return master.name
		return self._name
	@name.setter
	def name(self, value):
		self._name = value

class GSGlyph(GSBase):
	_classesForName = {
		"bottomKerningGroup": str,
		"bottomMetricsKey": str,
		"category": str,
		"color": color,
		"export":truthy,
		"glyphname": str,
		"lastChange": glyphs_datetime,
		"layers": GSLayer,
		"leftKerningGroup": str,
		"leftMetricsKey": str,
		"note": unicode,
		"partsSettings": dict,
		"production": str,
		"rightKerningGroup": str,
		"rightMetricsKey": str,
		"script": str,
		"subCategory": str,
		"topKerningGroup": str,
		"topMetricsKey": str,
		"unicode": str,
		"userData": dict,
		"vertWidthMetricsKey": str,
		"widthMetricsKey": str,
	}
	_wrapperKeysTranslate = {
		"glyphname" : "name"
	}
	def __init__(self):
		super(GSGlyph, self).__init__()
		self._layers = collections.OrderedDict()
		self.name = None
		self.parent = None
	
	def __repr__(self):
		return "<GSGlyph \"%s\" with %s layers>" % (self.name, len(self.layers))
		
	layers = property(	lambda self: GlyphLayerProxy(self),
						lambda self, value: GlyphLayerProxy(self).setter(value))
	
	def _setupLayer(self, layer, key):
		layer.parent = self
		layer.layerId = key
		try:
			if self.parent and self.parent.masterForId(key): # TODO use proxy `self.parent.masters[key]`
				layer.associatedMasterId = key
		except:
			print traceback.format_exc()
	# def setLayerForKey(self, layer, key):
	# 	if Layer and Key:
	# 		Layer.parent = self
	# 		Layer.layerId = Key
	# 		if self.parent.fontMasterForId(Key):
	# 			Layer.associatedMasterId = Key
	# 		self._layers[key] = layer

class GSFont(GSBase):
	_classesForName = {
		".appVersion": str,
		"DisplayStrings": [str],
		"classes": GSClass,
		"copyright": unicode,
		"customParameters": GSCustomParameter,
		"date": glyphs_datetime,
		"designer": unicode,
		"designerURL": unicode,
		"disablesAutomaticAlignment": truthy,
		"disablesNiceNames": truthy,
		"familyName": str,
		"featurePrefixes": GSClass,
		"features": GSFeature,
		"fontMaster": GSFontMaster,
		"glyphs": GSGlyph,
		"gridLength": int,
		"gridSubDivision": int,
		"instances": GSInstance,
		"keepAlternatesTogether": truthy,
		"kerning": dict,
		"manufacturer": unicode,
		"manufacturerURL": str,
		"unitsPerEm": int,
		"userData": dict,
		"versionMajor": int,
		"versionMinor": int,
	}
	_wrapperKeysTranslate = {
		".appVersion" : "appVersion",
		"fontMaster" : "masters",
	}
	def __init__(self):
		#super(GSBase, self).__init__()
		for key in self._classesForName.keys():
			try:
				value = self._classesForName[key]
				
				if isinstance(value, list) or issubclass(value, GSBase):
					value = []
				else:
					try:
						value = value().read(None)
					except:
						#print traceback.format_exc()
						value = value()
				setattr(self, key, value)
			except:
				print traceback.format_exc()
		self.familyName = "Unnamed font"
		self._versionMinor = 0
		self.versionMajor = 1
		self.appVersion = 0
		self._customParameters = []
	
	def __repr__(self):
		return "<%s \"%s\">" % (self.__class__.__name__, self.familyName)
	
	def getVersionMinor(self):
		return self._versionMinor
	
	def setVersionMinor(self, value):
		"""Ensure that the minor version number is between 0 and 999."""
		assert value >= 0 and value <= 999
		self._versionMinor = value
	
	versionMinor = property(getVersionMinor, setVersionMinor)
	
	@property
	def glyphs(self):
		return self._glyphs
	@glyphs.setter
	def glyphs(self, value):
		self._glyphs = value
		for g in self._glyphs:
			g.parent = self
			for layer in g.layers.values():
				if not hasattr(layer, "associatedMasterId") or layer.associatedMasterId is None or len(layer.associatedMasterId) == 0:
					
					g._setupLayer(layer, layer.layerId)
	
	@property
	def classes(self):
		return self._classes
	@classes.setter
	def classes(self, value):
		self._classes = value
		for g in self._classes:
			g.parent = self
	
	@property
	def features(self):
		return self._features
	@features.setter
	def features(self, value):
		self._features = value
		for g in self._features:
			g.parent = self
	
	@property
	def masters(self):
		return self._masters
	@masters.setter
	def masters(self, value):
		self._masters = value
		for m in self._masters:
			m.parent = self
	
	def masterForId(self, key):
		for master in self._masters:
			if master.id == key:
				return master
		return None
		
	@property
	def instances(self):
		return self._instances
	@instances.setter
	def instances(self, value):
		self._instances = value
		for i in self._instances:
			i.parent = self
	
	customParameters = property(lambda self: CustomParametersProxy(self),
								lambda self, value: CustomParametersProxy(self).setter(value))
