---
layout: page
title: Tools
permalink: /tools/
description: A growing collection of the tools I and my team made.
nav: true
nav_order: 4
display_categories: [work]
horizontal: false
---

<!-- pages/tools.md -->
<div class="tools">
{% if site.enable_tool_categories and page.display_categories %}
  <!-- Display categorized tools -->
  {% for category in page.display_categories %}
  <a id="{{ category }}" href=".#{{ category }}">
    <h2 class="category">{{ category }}</h2>
  </a>
  {% assign categorized_tools = site.tools | where: "category", category %}
  {% assign sorted_tools = categorized_tools | sort: "importance" %}
  <!-- Generate cards for each tool -->
  {% if page.horizontal %}
  <div class="container">
    <div class="row row-cols-2">
    {% for tool in sorted_tools %}
      {% include tools_horizontal.liquid %}
    {% endfor %}
    </div>
  </div>
  {% else %}
  <div class="grid">
    {% for tool in sorted_tools %}
      {% include tools.liquid %}
    {% endfor %}
  </div>
  {% endif %}
  {% endfor %}

{% else %}

<!-- Display tools without categories -->

{% assign sorted_tools = site.tools | sort: "importance" %}

  <!-- Generate cards for each tool -->

{% if page.horizontal %}

  <div class="container">
    <div class="row row-cols-2">
    {% for tool in sorted_tools %}
      {% include tools_horizontal.liquid %}
    {% endfor %}
    </div>
  </div>
  {% else %}
  <div class="grid">
    {% for tool in sorted_tools %}
      {% include tools.liquid %}
    {% endfor %}
  </div>
  {% endif %}
{% endif %}
</div>
