#pragma once
#ifndef PRETTYPRINTER_H
#define PRETTYPRINTER_H

#include <QString>

class XhtmlFormatParser;

class PrettyPrinter
{

public:
    static QString PrettifyXhtml(const QString& source, XhtmlFormatParser& xfparser);

    static QString trimmed(const QString& text, const QString& chars);

    static QString condenseText(const QString& text);
    
    static QString RegexSub(const QString& regexp, const QString& alt_pattern, const QString& text, int max_count = 0);

};

#endif // PRETTYPRINTER_H


