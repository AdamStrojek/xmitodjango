'''
@author: Adam Strojek
'''

from xml.dom import minidom
from xml.sax.saxutils import unescape

XMI_NS = 'http://schema.omg.org/spec/XMI/2.1'
UML_NS = 'http://schema.omg.org/spec/UML/2.0'

DATATYPES_MAP = {
    'boolean':  'models.BooleanField',
    'char':     'models.CharField',
    'double':   'models.DecimalField',
    'float':    'models.FloatField',
    'string':   'models.TextField',
    'int':      'models.IntegerField',
    'long':     'models.BigIntegerField',
    'date':     'models.DateField',
    'datetime': 'models.DateTimeField',
    'time':     'models.TimeField',
}

RELATIONSHIP_MAP = {
    'onetoone':     'models.OneToOne',
    'onetomany':    'models.ForeignKey',
    'manytomany':   'models.ManyToMany',
    }

import re
newline_re = re.compile('(?:\n|\r\n|\n\r|\r)', re.M)

class DjangoClass(object):
    '''
    classdocs
    '''

    def __init__(self, parent):
        '''
        Constructor
        '''
        self.parent = parent
        
        self.type = None
        self.xmi_id = None
        self.application = None
        self.name = None
        self.abstract = False
        self.attributes = []
        self.associations = []
        self.operations = []
    
    def _parseXmi(self, root):
        self.name = root.getAttribute('name')
        
        abstract = root.getAttribute('isAbstract')
        
        self.abstract = {'true': True, 'false': False}[abstract]
        
        parentNode = root.parentNode
        
        if parentNode.getAttributeNS(XMI_NS, 'type') == 'uml:Package':
            extensions = parentNode.getElementsByTagNameNS(XMI_NS, 'Extension')
            for extension in extensions:
                if len(extension.getElementsByTagName('appliedStereotype')) != 0:
                    stereotype = extension.getElementsByTagName('appliedStereotype')[0]
                    stereotype = self.parent.stereotypes[stereotype.getAttributeNS(XMI_NS, 'value')]
                    break
            if stereotype == 'DjangoApplication':
                self.application = parentNode.getAttribute('name')
        
        extensions = root.getElementsByTagNameNS(XMI_NS, 'Extension')
        for extension in extensions:
            if len(extension.getElementsByTagName('appliedStereotype')) != 0:
                stereotype = extension.getElementsByTagName('appliedStereotype')[0]
                self.type = self.parent.stereotypes[stereotype.getAttributeNS(XMI_NS, 'value')]
                break
        
        for attribute in root.getElementsByTagName('ownedAttribute'):
            self._parseAttribute(attribute)
        
        for operation in root.getElementsByTagName('ownedOperation'):
            self._parseOperation(operation)
    
    def _parseAttribute(self, root):
        name = root.getAttribute('name')
        datatype = self.parent.datatypes[root.getAttribute('type')]
        taggedValues = {'unique': 'True'}
        
        # Default value
        defautlValues = root.getElementsByTagName('defaultValue')
        for defaultValue in defautlValues:
            taggedValues['default'] = unescape(defaultValue.getAttribute('value'))
            
            if taggedValues['default'] == '':
                del taggedValues['default']
            
        # Getting comment as help text
        comments = root.getElementsByTagName('ownedComment')
        for comment in comments:
            body = comment.getElementsByTagName('body')[0].firstChild
            taggedValues['help_text'] = repr(body.wholeText)
        
        # Using tagged values to get rest informations
        extensions = root.getElementsByTagNameNS(XMI_NS, 'Extension')
        for extension in extensions:
            tags = []
            tags += extension.getElementsByTagName('unique')
            tags += extension.getElementsByTagName('taggedValue')
            for tag in tags:
                if tag.localName == 'unique' and tag.getAttributeNS(XMI_NS, 'value') != 'true':
                    del taggedValues['unique']
                elif tag.localName == 'taggedValue' and tag.getAttributeNS(XMI_NS, 'type') == 'uml:TaggedValue' and tag.getAttribute('tag').startswith('django_'):
                    tag_name = tag.getAttribute('tag')[7:]
                    taggedValues[tag_name] = unescape(tag.getAttribute('value')) 
                    if '' == taggedValues[tag_name]:
                        del taggedValues[tag_name]
                    
        tags = []
        for item in taggedValues.items():
            tags.append('%s=%s' % item)
        self.attributes.append('%s = %s(%s)' % (name, DATATYPES_MAP[datatype], ', '.join(tags)))
        
    def _parseAssociation(self, end_name, related_name, end_type, foreign_end):
        if related_name != '':
            self.associations.append("%s = %s('%s', related_name='%s')" % (end_name, RELATIONSHIP_MAP[end_type], foreign_end.getFullName(), related_name))
        else:
            self.associations.append("%s = %s('%s')" % (end_name, RELATIONSHIP_MAP[end_type], foreign_end.getFullName()))
    
    def _parseOperation(self, root):
        name = root.getAttribute('name')
        parametrs = []
        finalStatement = 'pass'
        
        for parametr in root.getElementsByTagName('ownedParameter'):
            if parametr.getAttribute('kind') in ('return'):
                if '' == parametr.getAttribute('type') or self.parent.datatypes[parametr.getAttribute('type')] != 'void':
                    finalStatement = 'return None'
            else:
                defaultValue = parametr.getElementsByTagName('defaultValue')
                if defaultValue.length == 0:
                    parametrs.append(parametr.getAttribute('name'))
                else:
                    parametrs.append(parametr.getAttribute('name') + '=' + defaultValue[0].getAttribute('value'))
        
        if self.type == 'DjangoModel':
            parametrs.insert(0, 'self')
        elif self.type == 'DjangoView':
            parametrs.insert(0, 'request')
        
        self.operations.append('def %s(%s):' % (name, ', '.join(parametrs)))
        
        # Getting comment as help text
        comments = root.getElementsByTagName('ownedComment')
        for comment in comments:
            body = comment.getElementsByTagName('body')[0].firstChild
            doc_comment = body.wholeText
            self.operations.append("    '''" )
            
            for line in newline_re.split(doc_comment):
                self.operations.append("    %s" % line )
            
            self.operations.append("    '''" )
        
        
        self.operations.append('    %s' % (finalStatement,))
    
    def isAbstract(self):
        return self.abstract
    
    def isValid(self):
        return (self.type == 'DjangoModel' and self.name != '') or self.type == 'DjangoView'
    
    def toDjango(self):
        
        tab = '' if self.type == 'DjangoView' else '    '
        
        string = ''
        
        if self.application is not None:
            string += '# Application: %s\n' %self.application
        
        if self.type == 'DjangoModel':
            string += 'class %s(models.Model):\n' % self.name
        
            for attribute in self.attributes:
                string += '%s%s\n' % (tab, attribute)
                
            for association in self.associations:
                string += '%s%s\n' % (tab, association)
        
        if len(self.operations):
            string += '\n'
        
        for operation in self.operations:
            string += '%s%s\n' % (tab, operation)
        
        if len(self.attributes) == len(self.associations) == len(self.operations) == 0:
            string += '%spass\n' % tab
        
        string += '\n'
        
        return string
    
    def getFullName(self):
        return '%s.%s' % (self.application, self.name) if self.application is not None else self.name
    
    def __repr__(self, *args, **kwargs):
        return '<DjangoClass: %s>' % self.getFullName()
