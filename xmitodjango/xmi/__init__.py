from xml.dom import minidom
from .xmi.models import DjangoClass

import os, os.path

XMI_NS = 'http://schema.omg.org/spec/XMI/2.1'
XMI_PREFIX = ''
UML_NS = 'http://schema.omg.org/spec/UML/2.0'
UML_PREFIX = ''

DJ_HEADER = {'DjangoModel': '''# Auto genereted file
from django.db import models
from django.contrib import admin

''',
        'DjangoView': '''# Auto genereted file
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response

'''}

class XMI(object):
    def __init__(self, *args, **kwargs):
        self.classes = {}
        self.associations = []
        
        self.stereotypes = {}
        self.datatypes = {}
        
        self.opened_files = {}
        
    def generate(self, path):
        for cls in self.classes.values():
            if cls.isAbstract():
                print 'Skipping generation for: ', cls.getFullName()
                continue
            
            local_path = os.path.join(path, cls.application)
            if cls.application is not None and not os.path.exists(local_path):
                os.mkdir(local_path)
                
                f = open(os.path.join(local_path, '__init__.py'), 'w')
                f.write('\n')
                f.close()
                
                print "Created directory:", local_path
                
            if cls.type == 'DjangoModel':
                file_name = 'models.py_gen'
            elif cls.type == 'DjangoView':
                file_name = 'views.py_gen'
            else:
                print 'Cannot generate file for: ', cls.type
                continue
            
            class_file = os.path.join(local_path, file_name)
            
            if class_file not in self.opened_files:
                print 'Generating file: ', class_file
                self.opened_files[class_file] = open(class_file, 'w')
                
                self.opened_files[class_file].write(DJ_HEADER[cls.type])
                
            self.opened_files[class_file].write(cls.toDjango())
        
        for f in self.opened_files.values():
            f.close()
        
        pass
        
    def parseFile(self, stream_or_string, parser=None, bufsize=None):
        self.document = minidom.parse(stream_or_string, parser, bufsize)
        self._parseXmi()
        
    def parseString(self, string, parser=None):
        self.document = minidom.parseString(string, parser)
        self._parseXmi()
        
    def _parseXmi(self):
        XMI = self.document.getElementsByTagNameNS(XMI_NS, 'XMI')[0]
        
        if XMI.getAttributeNS(XMI_NS, 'version') != '2.1':
            raise ValueError('Supports only 2.1 XMI files')
        
        model = XMI.getElementsByTagNameNS(UML_NS, 'Model')[0]
        
        clses = []
        assos = []
        
        for member in model.getElementsByTagName('ownedMember'):
            if member.getAttributeNS(XMI_NS, 'type') == 'uml:DataType':
                self.datatypes[member.getAttributeNS(XMI_NS, 'id')] = member.getAttribute('name')
            elif member.getAttributeNS(XMI_NS, 'type') == 'uml:Stereotype':
                self.stereotypes[member.getAttributeNS(XMI_NS, 'id')] = member.getAttribute('name')
            elif member.getAttributeNS(XMI_NS, 'type') == 'uml:Class':
                clses.append(member)
            elif member.getAttributeNS(XMI_NS, 'type') == 'uml:Association':
                assos.append(member)
                
        for cls in clses:
            cls_id = cls.getAttributeNS(XMI_NS, 'id')
            c = DjangoClass(self)
            c._parseXmi(cls)
            if c.isValid():
                self.classes[cls_id] = c
        
        for a in assos:
            self._parseAssociation(a)
        
    def _parseAssociation(self, root):
        ends = root.getElementsByTagName('ownedEnd')[:2]
        ends_desc = []
        
        prefferendEnd = None
        type_end = None
        foreignEnd = None
        
        for end in ends:
            end_desc = {
                'name': end.getAttribute('name'),
                'class': self.classes[end.getAttribute('type')],
            }
            
            lowerValueElements = end.getElementsByTagName('lowerValue')
            upperValueElements = end.getElementsByTagName('upperValue')
            
            if len(lowerValueElements):
                end_desc['lowerEnd'] = lowerValueElements[0].getAttribute('value')
            if len(upperValueElements):
                end_desc['upperEnd'] = upperValueElements[0].getAttribute('value')
                
            if 'lowerEnd' in end_desc:
                if 'upperEnd' not in end_desc or end_desc['lowerEnd'] == end_desc['upperEnd']:
                    end_desc['type'] = 'one'
                else:
                    end_desc['type'] = 'multi'
                    
            ends_desc.append(end_desc)
        
        if ends_desc[0]['type'] == 'one':
            prefferendEnd = ends_desc[0]
            foreignEnd = ends_desc[1]
            if ends_desc[1]['type'] == 'one':
                type_end = 'onetoone'
            else:
                type_end = 'onetomany'
        else:
            foreignEnd = ends_desc[0]
            if ends_desc[1]['type'] == 'one':
                prefferendEnd = ends_desc[1]
                type_end = 'onetomany'
            else:
                prefferendEnd = ends_desc[1]
                type_end = 'manytomany'
        
        prefferendEnd['class']._parseAssociation(prefferendEnd['name'], foreignEnd['name'], type_end, foreignEnd['class'])
            
        
