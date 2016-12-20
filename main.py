#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
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
#
import webapp2
import articleGrabber
import spamSorter
import json
import os
import logging
from google.appengine.api import users
from google.appengine.api import taskqueue

from database import Article
from database import Tag
from database import ProxyTag
from database import User

import datetime


import jinja2
from google.appengine.ext import ndb

import xml.etree.ElementTree

from urllib2 import urlopen
import sys
sys.path.insert(0, 'libs')
import xmltodict

DEVELOPMENT = True
BASE_URL = 'http://localhost:8080' if DEVELOPMENT else 'https://legalhackerarticlebot.appspot.com'
DATA_SOURCE = 'http://www.canlii.org/en/on/onca/rss_new.xml'

JINJA_ENVIRONMENT = jinja2.Environment(
                                       loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
                                       extensions=['jinja2.ext.autoescape'],
                                       autoescape=True

                                       )


# retrieve the current user and update the database to reflect
#   the current access as the last login time
def get_user():
    user = users.get_current_user()
    if user:
        db_user_record = User.get_or_insert(user.user_id())
        db_user_record.user = user.user_id()
        db_user_record.lastLoggedIn = datetime.datetime.now()
        db_user_record.put()
    return user


def get_tags(current_user, current_article):
    q1 = ProxyTag.query()
    q1 = q1.filter(ProxyTag.user == current_user.user_id())
    q1 = q1.filter(ProxyTag.article == current_article.key)
    q1 = q1.order(ProxyTag.score)
    return q1.get()


class AddTag(webapp2.RequestHandler):
    def post(self):
        key = self.request.get("Key")
        tag = self.request.get("Tag")
        db_article_record = ndb.Key(urlsafe=key).get()
        user = get_user()
        if not user:
            return
        q1 = Tag.query()
        q1 = q1.filter(Tag.scan == tag)
        q1 = q1.filter(Tag.user == user.user_id())
        a_tag = q1.get()
        if not a_tag:
            a_tag = Tag(scan=str(tag), scanKey=str(tag), user=user.user_id())
            a_tag.put()
        q1 = ProxyTag.query()
        q1 = q1.filter(ProxyTag.tag == a_tag.key)
        q1 = q1.filter(ProxyTag.article == db_article_record.key)
        q1 = q1.filter(ProxyTag.user == user.user_id())
        a_proxy = q1.get()
        if not a_proxy:
            # TODO determine if the assignment in the next line can be deleted
            a_proxy = ProxyTag(tag=a_tag.key, article=db_article_record.key, user=user.user_id()).put()
            queue = taskqueue.Queue(name='default')
            task = taskqueue.Task(
                url='/addToFilter',
                target='worker',
                params={'article': db_article_record.key.urlsafe(), 'tag': a_tag.scan, 'user': user.user_id()}
            )
            rpc = queue.add_async(task)
            # Wait for the rpc to complete and return the queued task.
            # TODO determine if the assignment in the following paragraph can be deleted
            task = rpc.get_result()
            self.response.out.write('Updated')
        else:
            self.response.out.write('Not Updated Already Present')


class RemoveTag(webapp2.RequestHandler):
    def post(self):
        key = self.request.get("Key")
        tag = self.request.get("Tag")
        article_key = ndb.Key(urlsafe=key).get().key
        user = get_user()
        if not user:
            return
        q1 = Tag.query()
        q1 = q1.filter(Tag.scan == tag)
        q1 = q1.filter(Tag.user == user.user_id())
        a_tag = q1.get()
        if not a_tag:
            a_tag = Tag(scan=str(tag), scanKey=str(tag), user=user.user_id())
            a_tag.put()
        q1 = ProxyTag.query()
        q1 = q1.filter(ProxyTag.tag == a_tag.key)
        q1 = q1.filter(ProxyTag.article == article_key)
        q1 = q1.filter(ProxyTag.user == user.user_id())
        a_proxy = q1.get()
        if a_proxy:
            if a_proxy.score == -1:
                self.response.out.write('Already Updated')
                return
            a_proxy.key.delete()
            # TODO determine if the assignment in the next line can be deleted
            a_proxy = ProxyTag(tag=a_tag.key, article=article_key, user=user.user_id(), score=-1).put()
            queue = taskqueue.Queue(name='default')
            task = taskqueue.Task(
                url='/RemoveFromFilter',
                target='worker',
                params={'article': article_key.urlsafe(), 'tag': a_tag.scan, 'user': user.user_id()})
            rpc = queue.add_async(task)
            # Wait for the rpc to complete and return the queued task.
            # TODO determine if the assignment in the next line, or the entire line, can be deleted
            task = rpc.get_result()
            self.response.out.write('Updated')
        else:
            self.response.out.write('Not Present')


# TODO why are there classes createTag and CreateTag (differing in name only by capitalization?)
#   consider renaming to better reflect their purpose or the naming convention of naming the
#   handler for the URL it's mapped to
class createTag(webapp2.RequestHandler):
    def post(self):
        key = self.request.get("Key")
        tag = self.request.get("Tag")
        # TODO the next line does not appear to serve any purpose
        an_article = ndb.Key(urlsafe=key).get()
        user = get_user()
        if user:
            tag_query = Tag.query()
            tag_query = tag_query.filter(Tag.user == user.user_id())
            tag_query = tag_query.filter(Tag.scan == tag)
            a_tag = tag_query.get()
            if not a_tag:
                a_tag = Tag(scan=str(tag), scanKey=str(tag), user=user.user_id())
                a_tag.put()
        self.response.out.write('Create Tag')


class RSSHandler(webapp2.RequestHandler):
    def get(self):
        data = {'base_url': BASE_URL}
        template = JINJA_ENVIRONMENT.get_template('rss.template')
        q1 = Article.query()
        q1 = q1.order(-Article.createDate)
        q1 = q1.filter(Article.createDate > datetime.datetime.now() - datetime.timedelta(hours=24))
        articles = []
        for aArt in q1:
            articles.append(aArt.json())
        data['Posts'] = articles
        self.response.headers['Content-Type'] = 'application/rss+xml'
        self.response.out.write(template.render(data))


class VoteData(webapp2.RequestHandler):
    def get(self):
        key = self.request.get("Key")
        an_article = ndb.Key(urlsafe=key).get()
        data = {'Post': an_article.json()}
        template = JINJA_ENVIRONMENT.get_template('Frame.html')
        self.response.out.write(template.render(data))


class VoteOnThis(webapp2.RequestHandler):
    def get(self):
        key = self.request.get("Key")
        current_article = ndb.Key(urlsafe=key).get()
        data = {}
        filters = []
        user = get_user()
        if user:
            data['LoggedIn'] = True
            q1 = Tag.query()
            q1 = q1.filter(Tag.user == user.user_id())
            for aFilter in q1:
                filters.append(aFilter.json())
            the_proxy = get_tags(user, current_article)
            if the_proxy:
                if the_proxy.score == -1:
                    data['Vote'] = {'Scan': 'No Tag', 'ScanKey': 'Unknown'}
                else:
                    data['Vote'] = the_proxy.json()
            else:
                data['Vote'] = {'Scan': 'Unknown', 'ScanKey': 'Unknown'}
        else:
            data['LoggedIn'] = False
        data['Post'] = current_article.json()
        url = users.create_logout_url("VoteData?Key="+key)
        data['Logout'] = url
        data['Filter'] = filters
        template = JINJA_ENVIRONMENT.get_template('Vote.html')
        self.response.out.write(template.render(data))


class GrabData(webapp2.RequestHandler):
    def get(self):
        datafile = urlopen(DATA_SOURCE)
        data = datafile.read()
        datafile.close()
        data = xmltodict.parse(data)
        for aDict in data['rss']['channel']['item']:
            a_article = Article.get_or_insert(aDict['link'])
            if a_article.indexed:
                continue
            a_article.title      = aDict['title']
            a_article.link       = aDict['link']
            a_article.casename   = aDict['decision:casename']
            a_article.citation   = aDict['decision:neutralCitation']
            a_article.officialReference   = aDict['decision:officialReference']
            a_article.decisionDate   = aDict['decision:decisionDate']
            a_article.pubDate   = aDict['pubDate']
            a_article.article = None
            a_article.put()
        self.response.write('New Data has been Grabbed')


class Login(webapp2.RequestHandler):
    def get(self):
        user = get_user()
        key = self.request.get("Key")
        if user:
            self.redirect('VoteData?Key=' + key)
        else:
            self.redirect(users.create_login_url('VoteData?Key=' + key))


class CreateTag(webapp2.RequestHandler):
    def get(self):
        data = {'Key': self.request.get("Key")}
        template = JINJA_ENVIRONMENT.get_template('CreateTag.html')
        self.response.out.write(template.render(data))


class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.response.out.write('Go to ' + BASE_URL + '/FindYourRSS to get your custom RSS Feed')


class FindYourRSS(webapp2.RequestHandler):
    def get(self):
        user = get_user()
        if user:
            db_user_record = User.get_or_insert(user.user_id())
            self.response.out.write(BASE_URL + '/YourRSS?Key='+db_user_record.key.urlsafe())
        else:
            self.redirect(users.create_login_url('/FindYourRSS'))


class YourRSS(webapp2.RequestHandler):
    def get(self):
        key = self.request.get("Key")
        current_user = ndb.Key(urlsafe=key).get()

        data = {'base_url': BASE_URL}
        template = JINJA_ENVIRONMENT.get_template('rss.template')
        q1 = Article.query()
        q1 = q1.order(-Article.createDate)
        q1 = q1.filter(Article.createDate > datetime.datetime.now() - datetime.timedelta(hours=24))
        articles = []
        for aArt in q1:
            if current_user:
                articles.append(aArt.jsonUser(current_user))
            else:
                articles.append(aArt.json())
        data['Posts'] = articles
        self.response.headers['Content-Type'] = 'application/rss+xml'
        self.response.out.write(template.render(data))


class AddTextToArticle(webapp2.RequestHandler):
    def get(self):
        q1 = Article.query()
        q1 = q1.order(-Article.createDate)
        q1 = q1.filter(not Article.articleCaptured)
        q1 = q1.filter(Article.createDate > datetime.datetime.now() - datetime.timedelta(hours=24))
        for anArticle in q1:
            queue = taskqueue.Queue(name='default')
            task = taskqueue.Task(
                url='/updateArticle',
                target='worker',
                params={'article': anArticle.key.urlsafe()})
            rpc = queue.add_async(task)
            # Wait for the rpc to complete and return the queued task.
            task = rpc.get_result()
            self.response.write(
                'Task {} enqueued, ETA {}.<br>'.format(task.name, task.eta))
        self.response.write('FileDone')


class DeleteAll(webapp2.RequestHandler):
    def get(self):
        q1 = ProxyTag.query()
        for aPTag in q1:
            aPTag.key.delete()

# TODO adopt a common capitalization convention for URLs
app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/addTag', AddTag),
    ('/removeTag', RemoveTag),
    ('/RSS', RSSHandler),
    ('/VoteData', VoteData),
    ('/VoteOnThis', VoteOnThis),
    ('/Login', Login),
    ('/Tag', CreateTag),
    ('/CreateTag', createTag),
    ('/GrabData', GrabData),
    ('/AddTextToArticle', AddTextToArticle),
    ('/DeleteAll', DeleteAll),
    ('/FindYourRSS', FindYourRSS),
    ('/YourRSS', YourRSS),
], debug=True)
