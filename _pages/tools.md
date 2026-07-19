---
layout: page
title: Tools
permalink: /tools/
description: A growing collection of the tools I and my team made.
nav: true
nav_order: 4
horizontal: false
body_class: research-stickers
---

<div class="tools sticker-board">
{% assign sorted_tools = site.tools | sort: "importance" %}
  <div class="sticker-board__grid">
    {% for tool in sorted_tools %}
      {% include tools.liquid index0=forloop.index0 %}
    {% endfor %}
  </div>
</div>
