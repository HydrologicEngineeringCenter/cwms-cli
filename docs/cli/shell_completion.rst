Shell Completion
================

``cwms-cli`` uses Click, which provides built-in shell completion support for
``bash`` (4.4+), ``zsh``, and ``fish`` when the CLI is installed as an entry
point such as ``cwms-cli``.

Shell completion can suggest:

- command and subcommand names
- option names
- values for supported parameter types such as choices and paths

See the official Click shell completion guide for background and advanced
customization:

- https://click.palletsprojects.com/en/stable/shell-completion/

Requirements
------------

- Install ``cwms-cli`` so the ``cwms-cli`` executable is available in your
  shell.
- Start completion from the installed command name, not ``python -m``.
- Restart your shell after changing your shell startup files.

Bash
----

Add this line to ``~/.bashrc``:

.. code-block:: bash

   eval "$(_CWMS_CLI_COMPLETE=bash_source cwms-cli)"

That asks Click to generate the completion script each time a new shell starts.

If you prefer to generate the script once and source a saved file instead:

.. code-block:: bash

   _CWMS_CLI_COMPLETE=bash_source cwms-cli > ~/.cwms-cli-complete.bash

Then add this line to ``~/.bashrc``:

.. code-block:: bash

   . ~/.cwms-cli-complete.bash

Zsh
---

Add this line to ``~/.zshrc``:

.. code-block:: zsh

   eval "$(_CWMS_CLI_COMPLETE=zsh_source cwms-cli)"

If you prefer to generate the script once and source a saved file instead:

.. code-block:: zsh

   _CWMS_CLI_COMPLETE=zsh_source cwms-cli > ~/.cwms-cli-complete.zsh

Then add this line to ``~/.zshrc``:

.. code-block:: zsh

   . ~/.cwms-cli-complete.zsh

Fish
----

Save the generated completion script to Fish's completions directory:

.. code-block:: fish

   _CWMS_CLI_COMPLETE=fish_source cwms-cli > ~/.config/fish/completions/cwms-cli.fish

Fish will load that file automatically in new shell sessions.

Verify Completion
-----------------

After installing the shell integration and opening a new shell, try:

.. code-block:: bash

   cwms-cli <TAB>

You should see top-level commands such as ``load``, ``usgs``, and ``blob``.
You can also try:

.. code-block:: bash

   cwms-cli load <TAB>
   cwms-cli blob --<TAB>

Unsupported Shells
------------------

Click's built-in shell completion support covers ``bash``, ``zsh``, and
``fish``. For now, ``cwms-cli`` does not document built-in completion setup
for PowerShell or ``cmd.exe``.

If Windows shell completion becomes a requirement, that will need either a
custom completion integration or a third-party Click shell extension.
