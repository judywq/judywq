---
layout: page
title: VocQGen
github: https://github.com/judywq/VocQGen
demo_url: https://vocqgen.streamlit.app/
description: A vocabulary question generator
# img: assets/img/12.jpg
importance: 1
category: work
related_publications: true
---

## What is {{ page.title }}

A python program for automated generation of multiple-choice cloze vocabulary questions.
The program is built on the GPT-4 model, NLP libraries and Google Ngram.
It allows user upload of custom vocabulary list and returns complete quizzes in accordance with user specified parameters.

- The source code is available at: [{{ page.github }}]({{ page.github }})
- A web user interface is available at: [{{ page.demo_url }}]({{ page.demo_url }}) (Note: the demo is hosted on a free tier of Streamlit, so you might need to wake it up first.)
- Related publications: {% cite wang2024automated %}.
