import sys
sys.path.insert(0, 'libs')
from BeautifulSoup import BeautifulSoup as bs
import urlparse
from urllib2 import urlopen
from urllib import urlretrieve
import os

import logging

import re

from database import Article

from google.appengine.ext import ndb

from HTMLParser import HTMLParser

def getArticle(url):
    soup = bs(urlopen(url))
    theArticle = soup.find("div", { "class" : "WordSection1" })
    fullText = ""
    h = HTMLParser()
    for node in theArticle.findAll('p'):
        fullText = fullText+ ''.join(node.findAll(text=True))+' '
    fullText = h.unescape(fullText)
    fullText = re.sub('\[(.*?)\]', '', fullText)
    return fullText
'''
def articleGrabber(url):
    soup = bs(urlopen(url))
    for article in soup.findAll("div", { "class" : "the-content" }):
        title = article.h1.a.string
        link = article.h1.a['href']
        anArticle = Article.get_or_insert(link)
        if anArticle.indexed == True:
            continue
        anArticle.title = article.h1.a.string
        anArticle.link = link
        anArticle.article = getArticle(article.h1.a['href'])
        anArticle.indexed = True;
        anArticle.put()
'''
