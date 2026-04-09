#include <QRegularExpression>
#include "Parsers/XhtmlFormatParser.h"

/** When pretty printing xhtml the user would like control over the format chosen
 ** So this code parses the users prettyprinter.pcss file to determine where and
 ** when to inject new lines, add indentation, and condense text.
 **
 ** The prettyprinter.pcss is a pseudo css structure whose selectors may only include
 ** element (tag) names and immediate child descendant combinators that are also
 ** element names
 **
 ** There are 2 global parameters that must appear at the top of the css before
 ** any selectors.  They are *not* used inside braces '{'.
 **
 ** @css-fold: true|false;     # specifies whether the css of the style node is collapsed.
 **                            # true or false with default value false.
 **
 ** @indent: int1;             # specifies the number of spaces per indentation level
 **                            # range 0 to 4, default value is 2.
 **
 ** There are only 6 possible properties:
 **
 ** opentag-br: int1 int2;     # specifies the number of new lines added *before* (int1)
 **                            # and *after* (int2) an opening tag.  Each ranges from
 **                            # 0 to 9 with a default value of 0.
 **
 ** closetag-br: int1 int2;    # specifies the number of new lines added *before* (int1)
 **                            # and *after* (int2) a closing tag.  Each ranges from
 **                            # 0 to 9 with a default value of 0.
 **
 ** ind-adj int1;              # adjusts the indent level of the node.  Positive numbers
 **                            # advance the indent level, negative numbers reduce the
 **                            # indent level.  Range is -9 to 9.
 **                              
 ** inner-ind-adj: int1;       # adjusts the indentation level within a node but excluding
 **                            # the node itself. Positive numbers advance the indent level,
 **                            # negative numbers reduce the indent level.  Range is -9 to 9.
 **
 ** attr-fm-resv: true|false;  # specifies whether to preserve unnecessary spaces and newlines
 **                            # inside the opening tag itself. Range: true or false.
 **                            # Default is false.
 **
 ** text-fm-resv: true|false;  # specifies whether to preserve unnecessary spaces and newlines
 **                            # inside the text of that node. Range: true or false.
 **                            # Default is false.
 **
 ** Note: When line breaks after a closing tag and before an opening tag are *not* added
 **       but are instead collapsed to be the larger of the two values.
 **/
  
static const QString DEFAULT_CONF = "/* global settings */\n"
"  @indent 2;\n"
"  @css-fold false;\n"
"\n"
"  /* block-level elements */\n"
"  html, body, p, div, h1, h2, h3, h4, h5, h6, ol, ul, li, address, blockquote, dd, dl, fieldset, form, hr, nav, menu, pre, table, tr, td, th, article {\n"
"      opentag-br : 1 0;\n"
"      closetag-br: 0 1;\n"
"  }\n"
"  p, div {\n"
"      opentag-br : 1 0;\n"
"      closetag-br: 0 2;\n"
"  }\n"
"\n"
"  /* head elements */\n"
"  head, meta, link, title, style, script {\n"
"      opentag-br : 1 0;\n"
"      closetag-br: 0 1;\n"
"  }\n"
"\n"
"  /* xml header */\n"
"  ?xml {\n"
"      opentag-br: 0 1;\n"
"  }\n"
"\n"
"  /* doctype */\n"
"  !DOCTYPE {\n"
"      opentag-br  : 1 2;\n"
"      attr-fm-resv: true;\n"
"  }\n" 
"\n"
"  /* xhtml element */\n"
"  html {\n"
"    inner-ind-adj:-1;\n"
"  }\n"
"\n"
"  /* comment */\n"
"  !-- {\n"
"      attr-fm-resv: true;\n"
"  }\n"
"\n"
"  /* main */\n"
"  body {\n"
"      opentag-br : 2 1;\n"
"      closetag-br: 1 1;\n"
"  }\n"
"\n"
"  h1,h2,h3,h4,h5,h6 {\n"
"      opentag-br : 2 0;\n"
"      closetag-br: 0 2;\n"
"  }\n"
"\n"
"  pre {\n"
"    text-fm-resv: true;\n"
"  }\n";

//------------------- XHTML Format Configure ------------------------


XhtmlFormatParser::XhtmlFormatParser(QString conf_text)
    : m_oriConfText(conf_text)
{
    if (m_oriConfText.isEmpty()) {
        m_oriConfText = getDefaultConfigure();
    }
    parse();
}


void XhtmlFormatParser::parse()
{
    QString clean_text = getCleanConfText();

    QRegularExpression test_int("^-?\\d+$");
    QRegularExpression test_int_int("^\\d+ \\d+$");
    QRegularExpression test_bool("true|false");
    QRegularExpression test_invalid_wildcard("[^ ]\\*|\\*[^ :]");
    QRegularExpression re;

    re.setPattern("@indent (\\d+);");
    QRegularExpressionMatch m = re.match(clean_text);
    if (m.hasMatch()) {
        int indent_size = m.captured(1).toInt();
        m_gobal_props.indent = indent_size;
    }
    re.setPattern("@css-fold (true|false);");
    m = re.match(clean_text);
    if (m.hasMatch()) {
        int cssfold_value = m.captured(1) == "true" ? 1 : 0;
        m_gobal_props.cssfold = cssfold_value;
    }

    re.setPattern("([a-zA-Z?!_\\-\\*][a-zA-Z\\d_,\\- \\*]*?)\\{(.*?)\\}");
    QRegularExpressionMatchIterator iter = re.globalMatch(clean_text);
    while (iter.hasNext()) {
        QRegularExpressionMatch m = iter.next();
        QString selectors = m.captured(1);
        QString properties = m.captured(2);
        foreach(QString sel, selectors.split(",")) {
            if (sel.indexOf(test_invalid_wildcard) > -1) continue;
            if (m_selectors.indexOf(sel) > -1) {
                m_selectors.removeAt(m_selectors.indexOf(sel));
            }
            m_selectors.append(sel);
            foreach(QString prop, properties.split(";")) {
                QStringList prop_value = prop.split(":");
                if (prop_value.length() != 2) continue;
                if (prop_value[0] == "opentag-br") {
                    if (prop_value[1].indexOf(test_int_int) < 0) continue;
                    QStringList values = prop_value[1].split(' ');
                    m_propertiesMap[sel].open_pre_br = values[0].toShort();
                    m_propertiesMap[sel].open_post_br = values[1].toShort();
                }
                else if (prop_value[0] == "closetag-br") {
                    if (prop_value[1].indexOf(test_int_int) < 0) continue;
                    QStringList values = prop_value[1].split(' ');
                    m_propertiesMap[sel].close_pre_br = values[0].toShort();
                    m_propertiesMap[sel].close_post_br = values[1].toShort();
                }
                else if (prop_value[0] == "ind-adj") {
                    if (prop_value[1].indexOf(test_int) < 0) continue;
                    m_propertiesMap[sel].ind_adj = prop_value[1].toShort();
                }
                else if (prop_value[0] == "inner-ind-adj") {
                    if (prop_value[1].indexOf(test_int) < 0) continue;
                    m_propertiesMap[sel].inner_ind_adj = prop_value[1].toShort();
                }
                else if (prop_value[0] == "attr-fm-resv") {
                    if (prop_value[1].indexOf(test_bool) < 0) continue;
                    m_propertiesMap[sel].attr_fm_resv = prop_value[1] == "true" ? 1 : 0;
                }
                else if (prop_value[0] == "text-fm-resv") {
                    if (prop_value[1].indexOf(test_bool) < 0) continue;
                    m_propertiesMap[sel].text_fm_resv = prop_value[1] == "true" ? 1 : 0;
                }
            }
        }
    }
}


QString XhtmlFormatParser::getConfText() {
    return m_oriConfText;
}


QString XhtmlFormatParser::getCleanConfText()
{
    QString text = m_oriConfText;
    QString new_text = "";
    QString blank_chars = " \n\t";
    bool annotation = false;
    // while brace > 0,the indicator inside the brace, while brace < 0, there are some unexpected right brace,the brace variable must be reset to 0.
    int index = -1;
    while (index < text.length() - 2)
    {
        ++index;
        QChar ch = text.at(index);
        QChar next_ch = text.at(index + 1);
        if (annotation) {
            if (ch == QChar('*') && next_ch == QChar('/')) {
                annotation = false;
                index += 1;
            }
            continue;
        }

        if (blank_chars.contains(ch)) {
            if (new_text == "") continue;
            if (blank_chars.contains(next_ch)) continue;
            if (QString("{};:,").contains(new_text.right(1))) continue;
            if (QString("{};:,").contains(next_ch)) continue;
        }

        if (ch == QChar('/') && next_ch == QChar('*')) {
            annotation = true;
            index += 1;
            continue;
        }
        new_text = blank_chars.contains(ch) ? new_text.append(" ") : new_text.append(ch);

    }// end while
    if (index == text.length() - 2 && text.right(1) != " ") {
        new_text += text.right(1);
    }
    return new_text;
}


ulong XhtmlFormatParser::calcWeightForSelector(QString selector) {
    QChar lastChar;
    ulong weight = 0;
    QStringList segments= selector.split(" ");
    foreach(QString seg, segments) {
        if (seg == "*") {
            weight += 1;
        }
        else {
            weight += 1000;
        }
    }
    return weight;
}


QStringList XhtmlFormatParser::OrderingSelectors(bool descending)
{
    QStringList orderedSelectors;
    QList<std::pair<QString, ulong>> selectorsWithWeight;
    unsigned int order = -1;
    foreach(QString sel, m_selectors)
    {
        order += 1;
        ulong weight = calcWeightForSelector(sel)*1000 + order;
        selectorsWithWeight << std::pair<QString,ulong>(sel, weight);
    }
    std::sort(selectorsWithWeight.begin(), selectorsWithWeight.end(), 
        [&descending](std::pair<QString, ulong> a, std::pair<QString, ulong> b) {
            if (descending) {
                return a.second > b.second;
            }
            return a.second < b.second;
        });
    foreach(auto selWithWeight, selectorsWithWeight) {
        orderedSelectors << selWithWeight.first;
    }
    return orderedSelectors;
}


QStringList XhtmlFormatParser::getAllSelectors(sort_mode mode) 
{
    switch (mode) {
    case ORI:
        return m_selectors;
    case ASCEND:
        return OrderingSelectors(false);
    case DESCEND:
        return OrderingSelectors(true);
    default:
        return m_selectors;
    }
}


XhtmlFormatParser::properties XhtmlFormatParser::getSelectorProperties(QString selector)
{
    if (m_propertiesMap.contains(selector)) {
        return m_propertiesMap.value(selector);
    }
    else {
        XhtmlFormatParser::properties default_props;
        return default_props;
    }
}


QString XhtmlFormatParser::getDefaultConfigure()
{
    return DEFAULT_CONF;
}
