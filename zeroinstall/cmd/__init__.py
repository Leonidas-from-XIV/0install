"""
The B{0install} command-line interface.
"""

# Copyright (C) 2011, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

from zeroinstall import _, logger
import os, sys
from optparse import OptionParser
import logging

from zeroinstall import SafeException, DryRun

valid_commands = ['add', 'select', 'show', 'download', 'run', 'update', 'whatchanged', 'destroy',
		  'config', 'import', 'list', 'add-feed', 'remove-feed', 'list-feeds',
		  'man', 'digest']

class UsageError(Exception): pass

def _ensure_standard_fds():
	"Ensure stdin, stdout and stderr FDs exist, to avoid confusion."
	for std in (0, 1, 2):
		try:
			os.fstat(std)
		except OSError:
			fd = os.open(os.devnull, os.O_RDONLY)
			if fd != std:
				os.dup2(fd, std)
				os.close(fd)

def _no_command(command_args):
	"""Handle --help and --version"""
	parser = OptionParser(usage=_("usage: %prog COMMAND\n\nTry --help with one of these:") +
			"\n\n0install " + '\n0install '.join(valid_commands))
	parser.add_option("-V", "--version", help=_("display version information"), action='store_true')

	(options, args) = parser.parse_args(command_args)
	if options.version:
		import zeroinstall
		print("0install (zero-install) " + zeroinstall.version)
		print("Copyright (C) 2011 Thomas Leonard")
		print(_("This program comes with ABSOLUTELY NO WARRANTY,"
				"\nto the extent permitted by law."
				"\nYou may redistribute copies of this program"
				"\nunder the terms of the GNU Lesser General Public License."
				"\nFor more information about these matters, see the file named COPYING."))
		sys.exit(0)
	parser.print_help()
	sys.exit(2)

def main(command_args, config = None):
	"""Act as if 0install was run with the given arguments.
	@arg command_args: array of arguments (e.g. C{sys.argv[1:]})
	@type command_args: [str]
	"""
	_ensure_standard_fds()

	if config is None:
		from zeroinstall.injector.config import load_config
		config = load_config()

	# The first non-option argument is the command name (or "help" if none is found).
	command = None
	for i, arg in enumerate(command_args):
		if not arg.startswith('-'):
			command = arg
			del command_args[i]
			break
		elif arg == '--':
			break
	
	verbose = False
	try:
		if command is None:
			return _no_command(command_args)

		if command not in valid_commands:
			raise SafeException(_("Unknown sub-command '%s': try --help") % command)

		# Configure a parser for the given command
		module_name = command.replace('-', '_')
		cmd = __import__('zeroinstall.cmd.' + module_name, globals(), locals(), [module_name], 0)
		parser = OptionParser(usage=_("usage: %%prog %s [OPTIONS] %s") % (command, cmd.syntax))

		parser.add_option("-c", "--console", help=_("never use GUI"), action='store_false', dest='gui')
		parser.add_option("", "--dry-run", help=_("just print what would be executed"), action='store_true')
		parser.add_option("-g", "--gui", help=_("show graphical policy editor"), action='store_true')
		parser.add_option("-v", "--verbose", help=_("more verbose output"), action='count')
		parser.add_option("", "--with-store", help=_("add an implementation cache"), action='append', metavar='DIR')

		cmd.add_options(parser)
		(options, args) = parser.parse_args(command_args)
		verbose = options.verbose

		if options.verbose:
			if options.verbose == 1:
				logger.setLevel(logging.INFO)
			else:
				logger.setLevel(logging.DEBUG)
			import zeroinstall
			logger.info(_("Running 0install %(version)s %(args)s; Python %(python_version)s"), {'version': zeroinstall.version, 'args': repr(command_args), 'python_version': sys.version})

		if options.with_store:
			from zeroinstall import zerostore
			for x in options.with_store:
				config.stores.stores.append(zerostore.Store(os.path.abspath(x)))
			logger.info(_("Stores search path is now %s"), config.stores.stores)

		if hasattr(options, 'dry_run'):
			config.handler.dry_run = bool(options.dry_run)

		cmd.handle(config, options, args)
	except KeyboardInterrupt:
		logger.info("KeyboardInterrupt")
		sys.exit(1)
	except UsageError:
		parser.print_help()
		sys.exit(1)
	except DryRun as ex:
		print(_("[dry-run]"), ex)
	except SafeException as ex:
		if verbose: raise
		try:
			from zeroinstall.support import unicode
			print(unicode(ex), file=sys.stderr)
		except:
			print(repr(ex), file=sys.stderr)
		sys.exit(1)
	return
