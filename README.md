# ArticleBot
A Bayesian Feed Filter for Caselaw

## Problem Statement

In common law jurisdictions like Ontario, new cases can mean new law. Some lawyers may want to stay up to date on any new law in their field of practice.  But there can be a lot of new cases to read, and they're not all relevant to everyone.

The proposed solution is a user-customized feed which allows a lawyer to specify one or more areas of law to follow.  The feed takes in all of the new case law, filters it down to the case law relevant to the user, and presents only those relevant cases to the user.

### Case Law Sources

Many Ontario cases are reported each day at [CanLII](http://www.canlii.org/).
CanLII has RSS feeds for [the Ontario Court of Appeal](http://www.canlii.org/en/on/onca/rss_new.xml), the [Ontario Superior Court of Justice](http://www.canlii.org/en/on/onsc/rss_new.xml) and the [Divisional Court](http://www.canlii.org/en/on/onscdc/rss_new.xml), among others.  (Of course, there's a feed for the [Supreme Court](http://www.canlii.org/en/ca/scc/rss_new.xml) too!)

### Machine learning to find relevant cases

By applying an algorithm to classify the caselaw and then filtering only for those areas of law that a user is interested in, the busy feeds can be filtered to a more manageable flow.  

A [Bayesian Classifier](https://en.wikipedia.org/wiki/Naive_Bayes_classifier) is one approach, in which the algorithm is trained on a sample from the existing caselaw corpus and then classifies new cases as they are announced on the RSS feed. 

One potential issue with this approach is that cases do not necessarily fit neatly into one area of law, while a simple sorter may only provide a single classification for a case.  For the filter to be most effective and reliable, the multiple classification problem must be resolved.

## A Note on CanLII's Terms of Service

This project might not comply of Section 6 of the [CanLII Terms of Service](http://www.canlii.org/en/info/terms.html) without the prior written consent of the CanLII editor.  Building a Bayesian classifier may either constitute bulk downloading or indexing in contravention of the terms of service.

