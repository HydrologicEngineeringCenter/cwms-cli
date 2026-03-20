Templates
=========

Template behavior depends on the selected engine and template kind.

Default table rendering
-----------------------

For standard table reports rendered with the ``text`` engine, no explicit
template block is required. The engine computes column widths and renders a
plain-text table from the report context.

Jinja templates
---------------

The ``jinja2`` engine renders a named template file. By default it looks in the
packaged reporting templates. You can also point it at a custom template
directory with ``engine.template_dir`` or ``--template-dir``.

Example:

.. code-block:: yaml

   engine:
     name: "jinja2"
     template: "report.html.j2"

``text_layout`` templates
-------------------------

Monthly text reports typically use:

.. code-block:: yaml

   template:
     kind: "text_layout"

``text_layout`` is section-driven. Each section describes how to emit one or
more lines. Common section types include:

* ``centered``
* ``blank``
* ``literal``
* ``fields``
* ``repeat``

Within those sections, ``parts`` can reference values from the report context
using ``path`` expressions such as ``summary.total_inflow`` or
``daily_rows`` items in a repeat block.

When to use each style
----------------------

Use the default text table when you want a compact operational table with
minimal configuration.

Use ``text_layout`` when the output must match an established fixed-format
layout.

Use Jinja2 when you need HTML, richer presentation, hyperlinks, or custom web
styling.
