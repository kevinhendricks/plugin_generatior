#ifndef TAG_LISTER
#define TAG_LISTER

#include <QStringList>
#include <QStringView>
#include <QList>

class QString;

class TagLister
{
public:

    struct TagInfo {
        int     pos;      // position of tag in source
        int     len;      // length of tag in source
        int     child;    // child number of this tag in its parent
        QString tpath;    // path of tag names to this tag ("." joined)
        QString tname;    // tag name, ?xml, ?, !--, !DOCTYPE, ![CDATA[
        QString ttype;    // xmlheader, pi, comment, doctype, cdata, begin, single, end
        int     open_pos; // set if end tag to position of its corresponding begin tag
        int     open_len; // set if end tag to length of its corresponding begin tag
    };

    struct AttInfo {
        int     pos;      // position of attribute relative to tag start
        int     len;      // length of attribute in tag
        int     vpos;     // position of attribute value relative to tag start
        int     vlen;     // length of attribute value
        QString aname;    // attribute name
        QString avalue;   // attribute value
    };


    TagLister();
    
    TagLister(const QString &source);
    ~TagLister() {};

    void reloadLister(const QString &source);

    const TagInfo& at(int i);
    size_t size();

    bool isPositionInBody(int pos);
    bool isPositionInTag(int pos);
    bool isPositionInOpenTag(int pos);
    bool isPositionInCloseTag(int pos);

    int findLastTagOnOrBefore(int pos);
    int findFirstTagOnOrAfter(int pos);
    int findOpenTagForClose(int i);
    int findCloseTagForOpen(int i);
    int findLastOpenOrSingleTagThatContainsYou(int pos);
    int findLastOpenTagOnOrBefore(int pos);
    int findBodyOpenTag();
    int findBodyCloseTag();
    QString GeneratePathToTag(int pos);

    const QString& getSource();

    static void parseAttribute(const QStringView tagstring, const QString &attribute_name, AttInfo& ainfo);
    static QString serializeAttribute(const QString &aname, const QString &avalue);
    static QString extractAllAttributes(const QStringView tagstring);
    
private:
    TagInfo getNext();
    void  buildTagList();
    QString makePathToTag();

    QStringView parseML();

    void parseTag(const QStringView tagstring, TagInfo &mi);

    int findTarget(const QString &tgt, int p, bool after=false);
    static int skipAnyBlanks(const QStringView segment, int p);
    static int stopWhenContains(const QStringView segment, const QString& stopchars, int p);

    static QString Substring(int start_index, int end_index, const QStringView string);
    static QString Substring(int start_index, int end_index, const QString &string)
    static QStringView SubstringView(int start_index, int end_index, const QString &string)
    
    QString        m_source;
    int            m_pos;
    int            m_next;
    int            m_child;
    QStringList    m_TagPath;
    QList<int>     m_TagPos;
    QList<int>     m_TagLen;
    QList<int>     m_TagChild;
    QList<TagInfo> m_Tags;
    int            m_bodyStartPos;
    int            m_bodyEndPos;
    int            m_bodyOpenTag;
    int            m_bodyCloseTag;
};

#endif
