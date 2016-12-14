from google.appengine.ext import ndb

def getTags(aUser,anArticle):
    q1 = ProxyTag.query()
    q1 = q1.filter(ProxyTag.user == aUser)
    q1 = q1.filter(ProxyTag.article == anArticle.key)
    q1 = q1.order(ProxyTag.score)
    return q1.get()


class User(ndb.Model):
    createDate          = ndb.DateTimeProperty(auto_now_add=True)
    lastLoggedIn        = ndb.DateTimeProperty(auto_now_add=True)
    user                = ndb.StringProperty(indexed=True)


class Tag(ndb.Model):
    createDate          = ndb.DateTimeProperty(auto_now_add=True)
    scan                = ndb.StringProperty(indexed=True)
    scanKey             = ndb.StringProperty(indexed=True)
    user                = ndb.StringProperty(indexed=True)

    def json(self):
        return {
            'Scan': self.scan,
            'ScanKey': self.scanKey,
            'User': self.user,
            'Key': self.key.urlsafe()
        }


class Article(ndb.Model):
    createDate          = ndb.DateTimeProperty(auto_now_add=True)
    title               = ndb.StringProperty(indexed=False)
    article             = ndb.TextProperty()
    articleCaptured     = ndb.BooleanProperty(default=False)
    link                = ndb.StringProperty(indexed=False)
    indexed             = ndb.BooleanProperty(indexed=False, default=False)
    chosen              = ndb.BooleanProperty(default=False)
    casename            = ndb.StringProperty(indexed=False)
    citation            = ndb.StringProperty(indexed=False)
    officialReference   = ndb.StringProperty(indexed=False)
    decisionDate        = ndb.StringProperty(indexed=False)
    pubDate             = ndb.StringProperty(indexed=False)

    def jsonUser(self, user):
            data = self.json()
            data['LoggedIn'] = True
            the_proxy = getTags(user.user, self)
            if the_proxy:
                if the_proxy.score == -1:
                    data['Scan'] = 'No Tag'
                else:
                    data['Scan'] = the_proxy.tag.get().scan
            else:
                data['Scan'] = 'No Tag'
            return data

    def json(self):
        return {
            'Title': self.title,
            'Article': self.article,
            'Link': self.link,
            'Key': self.key.urlsafe()
        }


class ProxyTag(ndb.Model):
    createDate          = ndb.DateTimeProperty(auto_now_add=True)
    tag                 = ndb.KeyProperty(kind=Tag)
    article             = ndb.KeyProperty(kind=Article)
    user                = ndb.StringProperty(indexed=True)
    score               = ndb.FloatProperty(indexed=True)
    computerGenerate    = ndb.BooleanProperty(default=False)

    def json(self):
        aTag = self.tag.get()
        data=aTag.json()
        data['Score']=self.score
        data['Computer']=self.computerGenerate
        return data


class Word(ndb.Model):
    stem = ndb.StringProperty(indexed=True)

    def grabKind(self, kind, user):
        scan = ScanType.get_or_insert(str(self.stem+"--"+kind+"--"+user))
        scan.kind = kind
        return scan


class ScanType(ndb.Model):
    word = ndb.KeyProperty(kind=Word)
    kind = ndb.StringProperty(indexed=True)
    spam = ndb.IntegerProperty(indexed=True, default=0)
    total = ndb.IntegerProperty(indexed=True, default=0)
