import sys
import os
import PrettyPrinter
from XhtmlFormatParser import XhtmlFormatParser

from PrettyPrinter import PrettyPrinter

def main():
    argv = sys.argv
    if len(argv) > 1:
        filepath = argv[1]
    if filepath:
        source = ""
        with open(filepath, 'r') as fp:
            source = fp.read()
    xfmtp = XhtmlFormatParser(open("prettyprinter.pcss").read())
    newsource = PrettyPrinter.PrettifyXhtml(source, xfmtp)
    print(newsource)
    return 0

if __name__ == '__main__':
    sys.exit(main())
