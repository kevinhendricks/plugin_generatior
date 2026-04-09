#include <QRegularExpression>
#include <QRegularExpressionMatch>

#include "TagLister.h"
#include "XhtmlFormatParser.h"
#include "PrettyPrinter.h"

#define tr QObject::tr


QString PrettyPrinter::RegexSub(const QString& regexp, const QString& alt_pattern, const QString& text, int max_count)
{
    QRegularExpression re(regexp);
    QString new_text = "";
    QRegularExpressionMatch match;
    int index = text.indexOf(re, 0, &match);
    int count = 0;
    int offset = 0;
    while (index > -1) {
        if (max_count > 0 && count == max_count) {
            break;
        }
        ++count;
        new_text += text.mid(offset, index - offset);
        if (match.hasMatch()) {
            offset = index + match.captured(0).length();
        }
        QString alt_text = "";
        bool backslash = false;
        foreach(QChar ch, alt_pattern) {
            if (ch == '\\') {
                backslash = true;
                continue;
            }
            if (backslash) {
                backslash = false;
                if (48 <= ch.unicode() && 57 >= ch.unicode()) {
                    int group_num = ch.unicode() - 48;
                    if (group_num <= match.lastCapturedIndex() + 1) {
                        alt_text += match.captured(group_num);
                        continue;
                    }
                }
                alt_text.append("\\");
            }
            alt_text.append(ch);
        }
        new_text += alt_text;
        index = text.indexOf(re, offset, &match);
    }
    new_text += text.mid(offset);
    return new_text;
}


QString PrettyPrinter::condenseText(const QString& text)
{
    QString segment = text;
    segment = segment.replace(QRegularExpression("(\\r\\n)|\\n|\\r"), " ");
    segment = segment.replace(QRegularExpression("\\s{2,}"), " ");
    return segment;
}


QString PrettyPrinter::trimmed(const QString& text, const QString& chars) {
    int i, j = 0;
    QChar ch;
    for (i = 0; i < text.size(); ++i) {
        ch = text.at(i);
        if (!chars.contains(ch)) break;
    }
    for (j = text.size() - 1; j >= 0; --j) {
        ch = text.at(j);
        if (!chars.contains(ch)) {
            ++j; break;
        }
    }
    return text.mid(i, j - i);
}

QString PrettyPrinter::PrettifyXhtml(const QString& source, XhtmlFormatParser& xfparser) {

    QString new_text = "";

    QStringList ascendSelectors = xfparser.getAllSelectors(XhtmlFormatParser::ASCEND);
    QStringList nodePath;

    auto isSelectorMatchNode = [&xfparser](QString& sel, QStringList& nodePath)->bool {
        QStringList segments = sel.split(" ");
        if (segments.size() > nodePath.size()) return false;
        bool isMatched = true;
        for (ushort i = 1; i <= segments.size(); ++i) {
            QString seg = segments.at(segments.size() - i);
            QString seg2 = nodePath.at(nodePath.size() - i);
            if (seg == "*") continue;
            if (seg != seg2) {
                isMatched = false;
                break;
            }
        }
        return isMatched;
    };
    ushort indentPara = xfparser.m_gobal_props.indent > 4 ? 2 : xfparser.m_gobal_props.indent < 0 ? 2 : xfparser.m_gobal_props.indent;
    ushort cssfold = xfparser.m_gobal_props.cssfold > 1 ? 0 : xfparser.m_gobal_props.cssfold < 0 ? 0 : xfparser.m_gobal_props.cssfold;

    auto calcFinalProps = [&ascendSelectors, &xfparser, &isSelectorMatchNode](QStringList& nodePath)->XhtmlFormatParser::properties {
        XhtmlFormatParser::properties finalProps;
        QString featurePath = nodePath.join(' ');

        if (xfparser.m_pathPropsCache.contains(featurePath))
            return xfparser.m_pathPropsCache[featurePath];

        foreach(QString sel, ascendSelectors) {
            if (isSelectorMatchNode(sel, nodePath)) {
                XhtmlFormatParser::properties props = xfparser.getSelectorProperties(sel);
                if (props.open_pre_br != XhtmlFormatParser::UNDEFINED_PROP) finalProps.open_pre_br = props.open_pre_br;
                if (props.open_post_br != XhtmlFormatParser::UNDEFINED_PROP) finalProps.open_post_br = props.open_post_br;
                if (props.close_pre_br != XhtmlFormatParser::UNDEFINED_PROP) finalProps.close_pre_br = props.close_pre_br;
                if (props.close_post_br != XhtmlFormatParser::UNDEFINED_PROP) finalProps.close_post_br = props.close_post_br;
                if (props.ind_adj != XhtmlFormatParser::UNDEFINED_PROP) finalProps.ind_adj = props.ind_adj;
                if (props.inner_ind_adj != XhtmlFormatParser::UNDEFINED_PROP) finalProps.inner_ind_adj = props.inner_ind_adj;
                if (props.attr_fm_resv != XhtmlFormatParser::UNDEFINED_PROP) finalProps.attr_fm_resv = props.attr_fm_resv;
                if (props.text_fm_resv != XhtmlFormatParser::UNDEFINED_PROP) finalProps.text_fm_resv = props.text_fm_resv;
            }
        }
        // Set default value
        finalProps.open_pre_br = finalProps.open_pre_br > 9 ? 0 : finalProps.open_pre_br < 0 ? 0 : finalProps.open_pre_br;
        finalProps.open_post_br = finalProps.open_post_br > 9 ? 0 : finalProps.open_post_br < 0 ? 0 : finalProps.open_post_br;
        finalProps.close_pre_br = finalProps.close_pre_br > 9 ? 0 : finalProps.close_pre_br < 0 ? 0 : finalProps.close_pre_br;
        finalProps.close_post_br = finalProps.close_post_br > 9 ? 0 : finalProps.close_post_br < 0 ? 0 : finalProps.close_post_br;
        finalProps.ind_adj = finalProps.ind_adj > 9 ? 0 : finalProps.ind_adj < -9 ? 0 : finalProps.ind_adj;
        finalProps.inner_ind_adj = finalProps.inner_ind_adj > 9 ? 0 : finalProps.inner_ind_adj < -9 ? 0 : finalProps.inner_ind_adj;
        finalProps.attr_fm_resv = finalProps.attr_fm_resv > 1 ? 0 : finalProps.attr_fm_resv < 0 ? 0 : finalProps.attr_fm_resv;
        finalProps.text_fm_resv = finalProps.text_fm_resv > 1 ? 0 : finalProps.text_fm_resv < 0 ? 0 : finalProps.text_fm_resv;

        xfparser.m_pathPropsCache[featurePath] = finalProps;
        return finalProps;
    };

    auto cleanOpenTagText = [](QString& opentag)->QString {
        QString new_tag = "", blank = "\n\t ", tight = "=;";
        for (unsigned int i = 0; i < opentag.size() - 1; i++) {
            QChar ch = opentag.at(i), next_ch = opentag.at(i + 1);
            if (blank.contains(ch)) {
                if (blank.contains(next_ch)) continue;
                if (tight.contains(next_ch) || tight.contains(new_tag.right(1))) continue;
            }
            new_tag.append(ch);
        }
        new_tag.append(opentag.right(1));
        return new_tag;
    };

    // tag.at(i)   represents the i-th tag.
    // ti.pos      represents the starting position of tag, with the "position line" located to left of left corner symbol"<",such as "xxxxxxx|<tag>xxxxxxxxxx", the "|" means the virtual position line.
    // ti.pos + ti.len    represents the closing position of tag, with the "position line" located to right of right corner symbol">",such as "xxxxxxx<tag>|xxxxxxxxxx".
    // ti.tname    represents the tag name.
    // ti.ttype    with value "begin" | "end" | "single" | "xmlheader" | "doctype" | "comment", the tname of type "comment" is written as "!--"

    TagLister taglist(source);
    int lvl = -1;
    TagLister::TagInfo lastTi = taglist.at(0);
    int lastPostBr = 0;
    int lastTagEndPos = 0;
    // The TagInfo at last of TagLister Obj is a dummy, we eliminate if
    unsigned int ti_count = taglist.size() - 1; 
    for (unsigned int i = 0; i < ti_count; ++i) {
        TagLister::TagInfo ti = taglist.at(i);
        QString previousText = ti.pos > lastTagEndPos ? trimmed(source.mid(lastTagEndPos, ti.pos - lastTagEndPos), " \n\t") : "";
        if (ti.ttype == "begin") {
            nodePath << ti.tname;
            XhtmlFormatParser::properties props = calcFinalProps(nodePath);
            lvl += 1 + props.ind_adj;
            QString pre_br = previousText.size() > 0 ? QString(props.open_pre_br, '\n') : props.open_pre_br > lastPostBr ? QString(props.open_pre_br - lastPostBr, '\n') : "";
            QString post_br = props.open_post_br > 0 ? QString(props.open_post_br, '\n') : "";
            QString indent = props.open_pre_br + lastPostBr == 0 ? "" : indentPara * lvl > 0 ? QString(indentPara * lvl, ' ') : "";
            QString tag = source.mid(ti.pos, ti.len);
            if (!props.attr_fm_resv) {
                tag = cleanOpenTagText(tag);
            }
            if (props.text_fm_resv) {
                post_br = "";
                i = taglist.findCloseTagForOpen(i) - 1; // The next index jump to closing tag directly
            } else {
                previousText = condenseText(previousText);
            }
            new_text += previousText + pre_br + indent + tag + post_br;
            lastPostBr = post_br.size();
            lvl += props.inner_ind_adj;

        } else if (ti.ttype == "end") {
            XhtmlFormatParser::properties props = calcFinalProps(nodePath);
            QString pre_br = previousText.size() > 0 ? QString(props.close_pre_br, '\n') : props.close_pre_br > lastPostBr ? QString(props.close_pre_br - lastPostBr, '\n') : "";
            QString post_br = props.close_post_br > 0 ? QString(props.close_post_br, '\n') : "";
            QString tag = source.mid(ti.pos, ti.len);
            lvl -= props.inner_ind_adj;
            QString indent = props.close_pre_br + lastPostBr == 0 ? "" : indentPara * lvl > 0 ? QString(indentPara * lvl, ' ') : "";

            if (ti.tname == "style") {
                // The "\v" is a unvisible char inserted by Code Generation of Emmet, 
                // indicates the insertion position of the Cursor, so we should not delete it here.
                if (previousText == "\v") {
                    previousText = "\n\v\n";
                } else if (trimmed(previousText, "\n\t ") != "") {
                    QString indent_ = indentPara * lvl > 0 ? QString(indentPara * lvl, ' ') : "";
                    CSSInfo* cp = new CSSInfo(previousText);
                    QString reformatCss = '\n' + cp->getReformattedCSSText(!cssfold) + '\n';
                    previousText = RegexSub("\n", "\n" + indent_, reformatCss);
                }
            }
            if (props.text_fm_resv) {
                previousText = source.mid(lastTagEndPos, ti.pos - lastTagEndPos);
                pre_br = "";
            } else {
                previousText = source.mid(lastTagEndPos, ti.pos - lastTagEndPos);
                previousText = condenseText(previousText);
            }
            new_text += previousText + pre_br + indent + tag + post_br;

            nodePath.pop_back();
            lastPostBr = post_br.size();
            lvl -= 1 + props.ind_adj;
            //--lvl;
        } else { // ti.ttype = "single" | "xmlheader" | "doctype" | "comment"
            nodePath << ti.tname;
            XhtmlFormatParser::properties props = calcFinalProps(nodePath);
            lvl += 1 + props.ind_adj;
            //++lvl;

            QString pre_br = previousText.size() > 0 ? QString(props.open_pre_br + props.close_pre_br, '\n') : props.open_pre_br + props.close_pre_br > lastPostBr ? QString(props.open_pre_br + props.close_pre_br - lastPostBr, '\n') : "";
            QString post_br = props.open_post_br + props.close_post_br > 0 ? QString(props.open_post_br + props.close_post_br, '\n') : "";
            QString indent = props.open_pre_br + lastPostBr == 0 ? "" : indentPara * lvl > 0 ? QString(indentPara * lvl, ' ') : "";
            QString tag = source.mid(ti.pos, ti.len);
            if (!props.attr_fm_resv) {
                tag = cleanOpenTagText(tag);
            }
            new_text += previousText + pre_br + indent + tag + post_br;

            nodePath.pop_back();
            lastPostBr = post_br.size();
            lvl -= 1 + props.ind_adj;
            //--lvl;
        }
        lastTagEndPos = ti.pos + ti.len;
    } // End of for loop
    return new_text;
}

