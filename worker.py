# Copyright 2016 Google Inc. All rights reserved.
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

# [START all]

from google.appengine.api import taskqueue
from google.appengine.ext import ndb
import webapp2
import logging
import spamSorter
import articleGrabber
import datetime

from database import ProxyTag
from database import User
from database import Tag

COUNTER_KEY = 'default counter'


class Counter(ndb.Model):
    count = ndb.IntegerProperty(indexed=False)


class UpdateCounterHandler(webapp2.RequestHandler):
    def post(self):
        amount = int(self.request.get('amount'))

        # This task should run at most once per second because of the datastore
        # transaction write throughput.
        @ndb.transactional
        def update_counter():
            counter = Counter.get_or_insert(COUNTER_KEY, count=0)
            counter.count += amount
            counter.put()

        update_counter()

class UpdateArticleHandler(webapp2.RequestHandler):
    def post(self):
        articleKey = self.request.get('article')
        aKey = ndb.Key(urlsafe=articleKey)
        anArticle = aKey.get()
        anArticle.article = articleGrabber.getArticle(anArticle.link);
        anArticle.articleCaptured = True
        anArticle.put()
        q1 = User.query()
        q1 = q1.filter(User.lastLoggedIn > datetime.datetime.now() - datetime.timedelta(hours=24));
        for aUser in q1:
            q2 = Tag.query()
            q2 = q2.filter(Tag.user == aUser.user)
            for aTag in q2:
                queue = taskqueue.Queue(name='default')
                task = taskqueue.Task(
                    url='/deployFilter',
                    target='worker',
                    params={'article': anArticle.key.urlsafe(), 'tag': aTag.key.urlsafe(), 'user': aUser.user})
                rpc = queue.add_async(task)
                # Wait for the rpc to complete and return the queued task.
                task = rpc.get_result()


class DeployFilter(webapp2.RequestHandler):
    def post(self):
        articleKey = self.request.get('article')
        aKey = ndb.Key(urlsafe=articleKey)
        anArticle = aKey.get()
        tag = self.request.get('tag')
        tag = ndb.Key(urlsafe=tag)
        tag = tag.get()
        user = self.request.get('user')
        q1 = ProxyTag.query()
        q1 = q1.filter(ProxyTag.tag == tag.key);
        q1 = q1.filter(ProxyTag.article == anArticle.key)
        q1 = q1.filter(ProxyTag.user == user)
        aProxy = q1.get()
        if aProxy == None:
            theValue = spamSorter._test_value(anArticle.article,tag.scanKey,user)
            aProxy = ProxyTag(tag=tag.key,article=anArticle.key,user=user,score=theValue,computerGenerate=True);
            aProxy.put()

class AddToFilter(webapp2.RequestHandler):
    def post(self):
        articleKey = self.request.get('article')
        aKey = ndb.Key(urlsafe=articleKey)
        anArticle = aKey.get()
        tag = self.request.get('tag')
        user = self.request.get('user')
        if anArticle.articleCaptured == False:
            anArticle.article = articleGrabber.getArticle(anArticle.link);
            anArticle.articleCaptured = True
            anArticle.put()
        spamSorter._update_text(anArticle.article,tag,user)

class RemoveFromFilter(webapp2.RequestHandler):
        def post(self):
            articleKey = self.request.get('article')
            aKey = ndb.Key(urlsafe=articleKey)
            anArticle = aKey.get()
            tag = self.request.get('tag')
            user = self.request.get('user')
            if anArticle.articleCaptured == False:
                anArticle.article = articleGrabber.getArticle(anArticle.link);
                anArticle.articleCaptured = True
                anArticle.put()
            spamSorter._update_text(anArticle.article,tag,user,True)


app = webapp2.WSGIApplication([
    ('/update_counter', UpdateCounterHandler),
    ('/updateArticle', UpdateArticleHandler),
    ('/deployFilter', DeployFilter),
    ('/addToFilter', AddToFilter),
], debug=True)
# [END all]
