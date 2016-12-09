# is_spam.py
# coding: utf-8

import sys
sys.path.insert(0, 'lib')
import re
import PPStemmer

#import cgi, cgitb
#cgitb.enable()
#from common import http_answer
import webapp2
from google.appengine.ext import ndb

from database import Word

split2words = re.compile(u'[^a-zA-Zа-яА-Я]+')

stop_words = set([
u'i', u'me', u'my', u'myself', u'we', u'our', u'ours', u'ourselves', u'you',
u'your', u'yours', u'yourself', u'yourselves', u'he', u'him', u'his',
u'himself', u'she', u'her', u'hers', u'herself', u'it', u'its', u'itself',
u'they', u'them', u'their', u'theirs', u'themselves', u'what', u'which',
u'who', u'whom', u'this', u'that', u'these', u'those', u'am', u'is', u'are',
u'was', u'were', u'be', u'been', u'being', u'have', u'has', u'had', u'having',
u'do', u'does', u'did', u'doing', u'a', u'an', u'the', u'and', u'but', u'if',
u'or', u'because', u'as', u'until', u'while', u'of', u'at', u'by', u'for',
u'with', u'about', u'against', u'between', u'into', u'through', u'during',
u'before', u'after', u'above', u'below', u'to', u'from', u'up', u'down', u'in',
u'out', u'on', u'off', u'over', u'under', u'again', u'further', u'then',
u'once', u'here', u'there', u'when', u'where', u'why', u'how', u'all', u'any',
u'both', u'each', u'few', u'more', u'most', u'other', u'some', u'such', u'no',
u'nor', u'not', u'only', u'own', u'same', u'so', u'than', u'too', u'very',
u's', u't', u'can', u'will', u'just', u'don', u'should', u'now'
])

def _filter_stop_words(word):
    return (word and word not in stop_words)

def _text_count_words(text):
    words = split2words.split(text)
    words = map(lambda x:x.lower(), words)

    words = filter(_filter_stop_words, words)
    words = map(PPStemmer.stem, words)

    counted_words = {}
    for w in words:
        if w in counted_words:
            counted_words[w] += 1
        else:
            counted_words[w] = 1

    return counted_words

def _update_text(text, typeV,user,clean = False):
    counted_words = _text_count_words(text)
    # save data
    writeList = []
    for w in counted_words.keys():
        count = counted_words[w]
        spam_count = count
        if clean == True:
            spam_count=0
        word = Word.get_by_id(w)
        if not word:
            word = Word(id=w)
            word.stem = w
            word.put()
        scanType = word.grabKind(typeV,user)
        scanType.total +=count
        scanType.spam += spam_count
        writeList.append(scanType)
    ndb.put_multi(writeList)

    return len(counted_words.keys())



def _test_value(text, typeV, user):
    counted_words = _text_count_words(text)
    words = counted_words.keys()
    weight = 0
    # hope I correctly get max portion size
    i, portion, wcount = 0, 30, len(words)
    while i < wcount:
        wportion = words[i:i+portion]
        i += portion
        ws = Word.gql("WHERE stem IN :1", wportion).fetch(portion)
        for word in ws:
            aKind = word.grabKind(typeV,user)
            if aKind.total == 0:
                continue
            word_weight = float(aKind.spam)/aKind.total
            word_count  = counted_words[word.stem]
            validity    = float(word_count)/wcount
            weight += validity * word_weight
    weight *= 100
    return weight;
