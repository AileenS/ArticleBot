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

import datetime

import webapp2
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

import articleGrabber
import spamSorter
from database import ProxyTag
from database import Tag
from database import User

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


class ArticleRequestHandler(webapp2.RequestHandler):
    def get_requested_article(self):
        requested_article_key = self.request.get('article')
        article = ndb.Key(urlsafe=requested_article_key).get()
        return article


class UpdateArticleHandler(ArticleRequestHandler):
    def post(self):
        article = self.get_requested_article()
        article.article = articleGrabber.getArticle(article.link)
        article.articleCaptured = True
        article.put()
        q1 = User.query()
        q1 = q1.filter(User.lastLoggedIn > datetime.datetime.now() - datetime.timedelta(hours=24))
        for aUser in q1:
            q2 = Tag.query()
            q2 = q2.filter(Tag.user == aUser.user)
            for aTag in q2:
                queue = taskqueue.Queue(name='default')
                task = taskqueue.Task(
                    url='/deployFilter',
                    target='worker',
                    params={'article': article.key.urlsafe(), 'tag': aTag.key.urlsafe(), 'user': aUser.user})
                rpc = queue.add_async(task)
                # Wait for the rpc to complete and return the queued task.
                # TODO determine if next line is necessary, or if the assignment should be removed
                task = rpc.get_result()


class DeployFilter(ArticleRequestHandler):
    def post(self):
        article = self.get_requested_article()
        tag = self._get_requested_tag()
        user = self.request.get('user')
        proxy = self._get_requested_proxy(article, tag, user)
        if proxy is None:
            the_value = spamSorter._test_value(article.article, tag.scanKey, user)
            proxy = ProxyTag(tag=tag.key, article=article.key, user=user, score=the_value, computerGenerate=True)
            proxy.put()

    def _get_requested_tag(self):
        tag = self.request.get('tag')
        tag = ndb.Key(urlsafe=tag)
        tag = tag.get()
        return tag

    @staticmethod
    def _get_requested_proxy(article, tag, user):
        q1 = ProxyTag.query()
        q1 = q1.filter(ProxyTag.tag == tag.key)
        q1 = q1.filter(ProxyTag.article == article.key)
        q1 = q1.filter(ProxyTag.user == user)
        proxy = q1.get()
        return proxy


class FilterModificationHandler(ArticleRequestHandler):
    def modify_filter(self, is_removal):
        article = self.get_requested_article()
        tag = self.request.get('tag')
        user = self.request.get('user')
        if not article.articleCaptured:
            article.article = articleGrabber.getArticle(article.link)
            article.articleCaptured = True
            article.put()
        spamSorter._update_text(article.article, tag, user, is_removal)


class AddToFilter(FilterModificationHandler):
    def post(self):
        self.modify_filter(is_removal=False)


class RemoveFromFilter(FilterModificationHandler):
        def post(self):
            self.modify_filter(is_removal=True)


app = webapp2.WSGIApplication([
    ('/update_counter', UpdateCounterHandler),
    ('/updateArticle', UpdateArticleHandler),
    ('/deployFilter', DeployFilter),
    ('/addToFilter', AddToFilter),
], debug=True)
# [END all]
