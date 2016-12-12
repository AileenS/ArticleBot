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

JINJA_ENVIRONMENT = jinja2.Environment(
                                       loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
                                       extensions=['jinja2.ext.autoescape'],
                                       autoescape=True

                                       )

def getUser():
    user = users.get_current_user()
    if user:
        aUser = User.get_or_insert(user.user_id())
        aUser.user = user.user_id()
        aUser.lastLoggedIn = datetime.datetime.now()
        aUser.put()
    return user




class AddTag(webapp2.RequestHandler):
    def post(self):
        key = self.request.get("Key");
        tag = self.request.get("Tag");
        aKey = ndb.Key(urlsafe=key)
        anArticle = aKey.get()
        user = getUser()
        if user:
            q1 = Tag.query();
            q1 = q1.filter(Tag.scan == tag);
            q1 = q1.filter(Tag.user == user.user_id());
            aTag = q1.get();
            if not aTag:
                aTag = Tag(scan=str(tag),scanKey=str(tag),user=user.user_id())
                aTag.put()
            q1 = ProxyTag.query();
            q1 = q1.filter(ProxyTag.tag==aTag.key)
            q1 = q1.filter(ProxyTag.article==anArticle.key)
            q1 = q1.filter(ProxyTag.user==user.user_id())
            aProxy = q1.get()
            if not aProxy:
                aProxy = ProxyTag(tag=aTag.key,article=anArticle.key,user=user.user_id()).put()
                queue = taskqueue.Queue(name='default')
                task = taskqueue.Task(
                url='/addToFilter',
                target='worker',
                params={'article': anArticle.key.urlsafe(), 'tag': aTag.scan, 'user': user.user_id()})
                rpc = queue.add_async(task)
                # Wait for the rpc to complete and return the queued task.
                task = rpc.get_result()
                self.response.out.write('Updated')
            else:
                self.response.out.write('Not Updated Already Present')

class RemoveTag(webapp2.RequestHandler):
    def post(self):
        key = self.request.get("Key");
        tag = self.request.get("Tag");
        aKey = ndb.Key(urlsafe=key)
        anArticle = aKey.get()
        user = getUser()
        if user:
            q1 = Tag.query();
            q1 = q1.filter(Tag.scan == tag);
            q1 = q1.filter(Tag.user == user.user_id());
            aTag = q1.get();
            if not aTag:
                aTag = Tag(scan=str(tag),scanKey=str(tag),user=user.user_id())
                aTag.put()
            q1 = ProxyTag.query();
            q1 = q1.filter(ProxyTag.tag==aTag.key)
            q1 = q1.filter(ProxyTag.article==anArticle.key)
            q1 = q1.filter(ProxyTag.user==user.user_id())
            aProxy = q1.get()
            if aProxy:
                if aProxy.score == -1:
                    self.response.out.write('Already Updated')
                    return
                aProxy.key.delete()
                aProxy = ProxyTag(tag=aTag.key,article=anArticle.key,user=user.user_id(),score=-1).put()
                queue = taskqueue.Queue(name='default')
                task = taskqueue.Task(
                url='/RemoveFromFilter',
                target='worker',
                params={'article': anArticle.key.urlsafe(), 'tag': aTag.scan, 'user': user.user_id()})
                rpc = queue.add_async(task)
                # Wait for the rpc to complete and return the queued task.
                task = rpc.get_result()
                self.response.out.write('Updated')
            else:
                self.response.out.write('Not Present')

class createTag(webapp2.RequestHandler):
    def post(self):
        key = self.request.get("Key");
        tag = self.request.get("Tag");
        aKey = ndb.Key(urlsafe=key)
        anArticle = aKey.get()
        user = getUser()
        if user:
            q1 = Tag.query();
            q1 = q1.filter(Tag.user == user.user_id());
            q1 = q1.filter(Tag.scan == tag);
            aTag = q1.get();
            if not aTag:
                aTag = Tag(scan=str(tag),scanKey=str(tag),user=user.user_id())
                aTag.put()
        self.response.out.write('Create Tag')


class RSSHandler(webapp2.RequestHandler):
    def get(self):
        data = {}
        template = JINJA_ENVIRONMENT.get_template('rss.template')
        q1 = Article.query()
        q1 = q1.order(-Article.createDate)
        q1 = q1.filter(Article.createDate > datetime.datetime.now() - datetime.timedelta(hours=24));
        articles = []
        for aArt in q1:
            articles.append(aArt.json())
        data['Posts'] = articles;
        self.response.headers['Content-Type'] = 'application/rss+xml'
        self.response.out.write(template.render(data))

class VoteData(webapp2.RequestHandler):
    def get(self):
        key = self.request.get("Key");
        aKey = ndb.Key(urlsafe=key)
        anArticle = aKey.get()
        data = {}
        data['Post']=anArticle.json()
        template = JINJA_ENVIRONMENT.get_template('Frame.html')
        self.response.out.write(template.render(data))


def getTags(aUser,anArticle):
    q1 = ProxyTag.query()
    q1 = q1.filter(ProxyTag.user == aUser.user_id())
    q1 = q1.filter(ProxyTag.article == anArticle.key)
    q1 = q1.order(ProxyTag.score)
    return q1.get()


class VoteOnThis(webapp2.RequestHandler):
    def get(self):
        key = self.request.get("Key");
        aKey = ndb.Key(urlsafe=key)
        anArticle = aKey.get()
        data = {}
        filters = []
        user = getUser()
        if user:
            data['LoggedIn']=True
            q1 = Tag.query();
            q1 = q1.filter(Tag.user == user.user_id());
            for aFilter in q1:
                filters.append(aFilter.json())
            theProxy =  getTags(user,anArticle)
            if theProxy:
                if theProxy.score==-1:
                    data['Vote']={'Scan':'No Tag','ScanKey':'Unknown'}
                else:
                    data['Vote']=theProxy.json();
            else:
                data['Vote']={'Scan':'Unknown','ScanKey':'Unknown'}
        else:
            data['LoggedIn']=False
        data['Post']=anArticle.json()
        url = users.create_logout_url("VoteData?Key="+key)
        data['Logout']=url
        data['Filter'] = filters
        template = JINJA_ENVIRONMENT.get_template('Vote.html')
        self.response.out.write(template.render(data))

from urllib2 import urlopen
import sys
sys.path.insert(0, 'libs')
import xmltodict

class GrabData(webapp2.RequestHandler):
    def get(self):
        file = urlopen('http://www.canlii.org/en/on/onca/rss_new.xml')
        data = file.read()
        file.close()
        data = xmltodict.parse(data)
        for aDict in data['rss']['channel']['item']:
            aArticle = Article.get_or_insert(aDict['link'])
            if aArticle.indexed == True:
                continue
            aArticle.title      = aDict['title']
            aArticle.link       = aDict['link']
            aArticle.casename   = aDict['decision:casename']
            aArticle.citation   = aDict['decision:neutralCitation']
            aArticle.officialReference   = aDict['decision:officialReference']
            aArticle.decisionDate   = aDict['decision:decisionDate']
            aArticle.pubDate   = aDict['pubDate']
            aArticle.article = None
            aArticle.put()
        self.response.write('New Data has been Grabbed')

class Login(webapp2.RequestHandler):
    def get(self):
        user = getUser()
        key = self.request.get("Key");
        if user:
            self.redirect('VoteData?Key='+ key)
        else:
            self.redirect(users.create_login_url('VoteData?Key='+ key))

class CreateTag(webapp2.RequestHandler):
    def get(self):
        data = {}
        data['Key']= self.request.get("Key");
        template = JINJA_ENVIRONMENT.get_template('CreateTag.html')
        self.response.out.write(template.render(data))

class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.response.out.write('Go to https://legalhackerarticlebot.appspot.com/FindYourRSS to get your custom RSS Feed')

class FindYourRSS(webapp2.RequestHandler):
    def get(self):
        user = getUser()
        if user:
            aUser = User.get_or_insert(user.user_id())
            self.response.out.write('https://legalhackerarticlebot.appspot.com/YourRSS?Key='+aUser.key.urlsafe())
        else:
            self.redirect(users.create_login_url('/FindYourRSS'))

class YourRSS(webapp2.RequestHandler):
    def get(self):
        key = self.request.get("Key");
        aKey = ndb.Key(urlsafe=key)
        aUser = aKey.get()
        if aUser:
            data = {}
            template = JINJA_ENVIRONMENT.get_template('rss.template')
            q1 = Article.query()
            q1 = q1.order(-Article.createDate)
            q1 = q1.filter(Article.createDate > datetime.datetime.now() - datetime.timedelta(hours=24));
            articles = []
            for aArt in q1:
                articles.append(aArt.jsonUser(aUser))
            data['Posts'] = articles;
            self.response.headers['Content-Type'] = 'application/rss+xml'
            self.response.out.write(template.render(data))
        else:
            data = {}
            template = JINJA_ENVIRONMENT.get_template('rss.template')
            q1 = Article.query()
            q1 = q1.order(-Article.createDate)
            q1 = q1.filter(Article.createDate > datetime.datetime.now() - datetime.timedelta(hours=24));
            articles = []
            for aArt in q1:
                articles.append(aArt.json())
            data['Posts'] = articles;
            self.response.headers['Content-Type'] = 'application/rss+xml'
            self.response.out.write(template.render(data))



class AddTextToArticle(webapp2.RequestHandler):
    def get(self):
        q1 = Article.query();
        q1 = q1.order(-Article.createDate)
        q1 = q1.filter(Article.articleCaptured==False);
        q1 = q1.filter(Article.createDate > datetime.datetime.now() - datetime.timedelta(hours=24));
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
        q1 = ProxyTag.query();
        for aPTag in q1:
            aPTag.key.delete()


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/addTag', AddTag),
    ('/removeTag',RemoveTag),
    ('/RSS', RSSHandler),
    ('/VoteData', VoteData),
    ('/VoteOnThis', VoteOnThis),
    ('/Login', Login),
    ('/Tag',CreateTag),
    ('/CreateTag',createTag),
    ('/GrabData',GrabData),
    ('/AddTextToArticle',AddTextToArticle),
    ('/DeleteAll',DeleteAll),
    ('/FindYourRSS',FindYourRSS),
    ('/YourRSS',YourRSS),


], debug=True)
