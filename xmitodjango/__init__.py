'''
@author: Adam Strojek
'''

from .xmi import XMI

def main(app_name, argv):
    
    if len(argv) < 2:
        print 'Not enought parametrs! Usage:'
        print app_name, '[path to XMI file]', '[path to Django Project directory]'
        exit(-1)
    
    xmi_file = XMI()
    xmi_file.parseFile(open(argv[0], 'r'))
    xmi_file.generate(argv[1])

if __name__ == '__main__':
    import sys
    
    main(sys.argv[0], sys.argv[1:] if len(sys.argv)>1 else [])
