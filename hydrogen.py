# -*- coding: utf-8 -*-
"""
    hydrogen
    ~~~~~~~~

    Hydrogen is an extremely lightweight workflow enhancement tool for Python
    web applications, providing bower/npm-like functionality for both pip and
    bower packages.

    :author: David Gidwani <david.gidwani@gmail.com>
    :license: BSD, see LICENSE for details
"""
import atexit
from collections import defaultdict
from functools import update_wrapper
import json
import os
import re
import shutil
import sys
import tempfile

import yaml
import zipfile

import click
import envoy
from pathlib import Path, PurePath
from pathspec import GitIgnorePattern, PathSpec
from pip._vendor import pkg_resources
import requests
import rfc6266
import semver


__version__ = "0.0.1-alpha"
prog_name = "hydrogen"
app_dir = click.get_app_dir(prog_name)
github_api_uri = "https://api.github.com"
debug = True


# borrowed from werkzeug._compat
PY2 = sys.version_info[0] == 2
if PY2:
    from urlparse import urlparse
    text_type = unicode  # noqa: Undefined in py3
else:
    from urllib.parse import urlparse
    text_type = str


class InvalidRequirementSpecError(Exception):
    pass


class InvalidPackageError(Exception):
    pass


class PackageNotFoundError(Exception):
    pass


class VersionNotFoundError(Exception):
    pass


def get_installed_pypackages():
    return {p.project_name.lower(): p for p in pkg_resources.working_set}


def success(message, **kwargs):
    kwargs["fg"] = kwargs.get("fg", "green")
    click.secho(message, **kwargs)


def warning(message, **kwargs):
    kwargs["fg"] = kwargs.get("fg", "red")
    click.secho(u"warning: {}".format(message), **kwargs)


def error(message, level="error", exit_code=1, **kwargs):
    kwargs["fg"] = kwargs.get("fg", "red")
    click.secho(u"error: {}".format(message), **kwargs)
    sys.exit(exit_code)


def fatal(message, **kwargs):
    error(message, level="fatal", **kwargs)


def secure_filename(filename):
    r"""Borrowed from :mod:`werkzeug.utils`, under the BSD 3-clause license.

    Pass it a filename and it will return a secure version of it.  This
    filename can then safely be stored on a regular file system and passed
    to :func:`os.path.join`.  The filename returned is an ASCII only string
    for maximum portability.

    On windows systems the function also makes sure that the file is not
    named after one of the special device files.

    >>> secure_filename("My cool movie.mov")
    'My_cool_movie.mov'
    >>> secure_filename("../../../etc/passwd")
    'etc_passwd'
    >>> secure_filename(u'i contain cool \xfcml\xe4uts.txt')
    'i_contain_cool_umlauts.txt'

    The function might return an empty filename.  It's your responsibility
    to ensure that the filename is unique and that you generate random
    filename if the function returned an empty one.

    :param filename: the filename to secure
    """
    _filename_ascii_strip_re = re.compile(r'[^A-Za-z0-9_.-]')
    _windows_device_files = ('CON', 'AUX', 'COM1', 'COM2', 'COM3', 'COM4',
                             'LPT1', 'LPT2', 'LPT3', 'PRN', 'NUL')
    if isinstance(filename, text_type):
        from unicodedata import normalize
        filename = normalize('NFKD', filename).encode('ascii', 'ignore')
        if not PY2:
            filename = filename.decode('ascii')
    for sep in os.path.sep, os.path.altsep:
        if sep:
            filename = filename.replace(sep, ' ')
    filename = str(_filename_ascii_strip_re.sub('', '_'.join(
                   filename.split()))).strip('._')

    # on nt a couple of special files are present in each folder.  We
    # have to ensure that the target file is not such a filename.  In
    # this case we prepend an underline
    if os.name == 'nt' and filename and \
       filename.split('.')[0].upper() in _windows_device_files:
        filename = '_' + filename

    return filename


def get(url, session=None, silent=not debug, **kwargs):
    """Retrieve a given URL and log response.

    :param session: a :class:`requests.Session` object.
    :param silent: if **True**, response status and URL will not be printed.
    """
    session = session or requests
    kwargs["verify"] = kwargs.get("verify", True)
    r = session.get(url, **kwargs)
    if not silent:
        status_code = click.style(
            str(r.status_code),
            fg="green" if r.status_code in (200, 304) else "red")
        click.echo(status_code + " " + url)
        if r.status_code == 404:
            raise PackageNotFoundError
    return r


def download_file(url, dest=None, chunk_size=1024, replace="ask",
                  label="Downloading {dest_basename} ({size:.2f}MB)",
                  expected_extension=None):
    """Download a file from a given URL and display progress.

    :param dest: If the destination exists and is a directory, the filename
        will be guessed from the Content-Disposition header. If the destination
        is an existing file, the user will either be prompted to overwrite, or
        the file will be replaced (depending on the value of **replace**). If
        the destination does not exist, it will be used as the filename.
    :param int chunk_size: bytes read in at a time.
    :param replace: If `False`, an existing destination file will not be
        overwritten.
    :param label: a string which is formatted and displayed as the progress bar
        label. Variables provided include *dest_basename*, *dest*, and *size*.
    :param expected_extension: if set, the filename will be sanitized to ensure
        it has the given extension. The extension should not start with a dot
        (`.`).
    """
    dest = Path(dest or url.split("/")[-1])
    response = get(url, stream=True)
    if (dest.exists()
            and dest.is_dir()
            and "Content-Disposition" in response.headers):
        content_disposition = rfc6266.parse_requests_response(response)
        if expected_extension is not None:
            filename = content_disposition.filename_sanitized(
                expected_extension)
        filename = secure_filename(filename)
        dest = dest / filename
    if dest.exists() and not dest.is_dir():
        if (replace is False
                or replace == "ask"
                and not click.confirm("Replace {}?".format(dest))):
            return str(dest)
    size = int(response.headers.get("content-length", 0))
    label = label.format(dest=dest, dest_basename=dest.name,
                         size=size/1024.0/1024)
    with click.open_file(str(dest), "wb") as f:
        content_iter = response.iter_content(chunk_size=chunk_size)
        with click.progressbar(content_iter, length=size/1024,
                               label=label) as bar:
            for chunk in bar:
                if chunk:
                    f.write(chunk)
                    f.flush()
    return str(dest)


def get_dir_from_zipfile(zip_file, fallback=None):
    """Return the name of the root folder in a zip file.

    :param zip_file: a :class:`zipfile.ZipFile` instance.
    :param fallback: if `None`, the name of the zip file is used. This is
        returned if the zip file contains more than one top-level directory,
        or none at all.
    """
    fallback = fallback or zip_file.filename
    directories = [name for name in zip_file.namelist() if name.endswith("/")
                   and len(PurePath(name).parts) == 1]
    return fallback if len(directories) > 1 else directories[0]


def mkdtemp(suffix="", prefix=__name__ + "_", dir=None, cleanup=True,
            on_cleanup_error=None):
    """Create a temporary directory and register a handler to cleanup on exit.

    :param suffix: suffix of the temporary directory, defaults to empty.
    :param prefix: prefix of the temporary directory, defaults to `__name__`
        and an underscore.
    :param dir: if provided, the directory will be created in `dir` rather than
        the system default temp directory.
    :param cleanup: if `True`, an atexit handler will be registered to remove
        the temp directory on exit.
    :param on_cleanup_error: a callback which is called if the atexit handler
        encounters an exception. It is passed three parameters: *function*,
        *path*, and *excinfo*. For more information, see the :mod:`atexit`
        documentation.
    """
    path = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
    if cleanup:
        if on_cleanup_error is None:
            def on_cleanup_error(function, path, excinfo):
                click.secho("warning: failed to remove file or directory: {}\n"
                            "please delete it manually.".format(path),
                            fg="red")
        atexit.register(shutil.rmtree, path=path, onerror=on_cleanup_error)
    return path


class Requirement(object):
    """Represents a single package requirement.

    .. note::
        This class overrides `__hash__` in order to ensure that package
        names remain unique when in a set.

    .. todo::
        Extend :class:`pkg_resources.Requirement` for Python requirements.
    """
    # TODO: support multiple version specs (e.g. >=1.0,<=2.0)
    spec_regex = r"(.+?)\s*(?:([<>~=]?=)\s*(.+?))?$"

    def __init__(self, package, version):
        """Construct a new requirement.

        :param package: the package name.
        :param version: a semver compatible version specification.
        """
        self.package = package
        self.version = version
        if self.version and not re.match(r"[<=>~]", version[:2]):
            self.version = "=={}".format(self.version)

    @classmethod
    def coerce(cls, string):
        """Create a :class:`Requirement` object from a given package spec."""
        match = re.match(cls.spec_regex, string)
        if not match:
            raise InvalidRequirementSpecError("could not parse requirement")
        package = match.group(1)
        if all(match.group(2, 3)):
            version = "".join(match.group(2, 3))
        else:
            version = None
        return cls(package, version)

    def load_installed_version(self):
        installed_packages = get_installed_pypackages()
        if self.package in installed_packages:
            self.version = "=={}".format(
                installed_packages[self.package].version)

    def __eq__(self, other):
        return (isinstance(other, self.__class__)
                and other.package == self.package)

    def __hash__(self):
        return hash(self.package)

    def __str__(self):
        return "".join([self.package, self.version or ""])

    def __repr__(self):
        return "<Requirement(package={package}, version='{version}')>".format(
            package=self.package, version=self.version)


class Requirements(set):
    """Represents a set of requirements."""
    def __init__(self, filename=None):
        self.filename = None
        if filename:
            self.load(filename)

    def add(self, elem, replace=False):
        """Add a requirement.

        :param elem: a string or :class:`Requirement` instance.
        :param replace: if `True`, packages in the set with the same name will
            be removed first.
        """
        if isinstance(elem, text_type):
            elem = Requirement.coerce(elem)
        if replace and elem in self:
            self.remove(elem)
        super(Requirements, self).add(elem)

    def load(self, requirements_file=None):
        """Load or reload requirements from a requirements.txt file.

        :param requirements_file: if not given, the filename used from
            initialization will be read again.
        """
        if requirements_file is None:
            requirements_file = self.filename
            if requirements_file is None:
                raise ValueError("no filename provided")
        elif isinstance(requirements_file, text_type):
            requirements_file = Path(requirements_file)
        self.clear()
        with requirements_file.open() as f:
            lines = re.findall(Requirement.spec_regex, f.read(), re.MULTILINE)
            for line in lines:
                self.add(Requirement(line[0], "".join(line[1:])))
        if isinstance(requirements_file, (text_type, Path)):
            self.filename = requirements_file

    def remove(self, elem):
        """Remove a requirement.

        :param elem: a string or :class:`Requirement` instance.
        """
        if isinstance(elem, text_type):
            for requirement in self:
                if requirement.package == elem:
                    return super(Requirements, self).remove(requirement)
        return super(Requirements, self).remove(elem)

    def __str__(self):
        return "\n".join(map(str, self))

    def __repr__(self):
        return "<Requirements({})>".format(self.filename.name or "")


class NamedRequirements(Requirements):
    def __init__(self, name, filename=None):
        self.name = name
        super(NamedRequirements, self).__init__(filename=filename)

    def __repr__(self):
        return "<NamedRequirements({}{})>".format(
            self.name,
            ", filename='{}'".format(self.filename.name) if self.filename
            else "")


class GroupedRequirements(defaultdict):
    default_groups = ["all", "dev", "bower", "bower-dev"]
    default_pip_files = {
        "all": "requirements.txt",
        "dev": "dev-requirements.txt"
    }

    def __init__(self, groups=None):
        super(GroupedRequirements, self).__init__(NamedRequirements)
        self.groups = groups or self.default_groups
        self.filename = None
        self.create_default_groups()

    def clear(self):
        super(GroupedRequirements, self).clear()
        self.create_default_groups()

    def create_default_groups(self):
        for group in self.groups:
            group = group.replace(" ", "_").lower()
            self[group] = NamedRequirements(group)

    def load_pip_requirements(self, files_map=None, freeze=True):
        if files_map is None:
            files_map = self.default_pip_files
        for group, requirements_txt in files_map.items():
            path = Path(requirements_txt)
            if not path.exists() and group.lower() == "all" and freeze:
                cmd = envoy.run("pip freeze")
                self[group].load(cmd.std_out)
            elif path.exists():
                self[group].load(path)

    def load(self, filename, create_if_missing=True):
        filename = Path(filename)
        if not filename.exists() and create_if_missing:
            self.load_pip_requirements()
            with filename.open("w") as f:
                f.write(yaml.dump(self.serialized, default_flow_style=False,
                                  encoding=None))
            self.filename = filename
            return self.save(filename)
        with filename.open() as f:
            for group, requirements in yaml.load(f.read()).items():
                for requirement in requirements:
                    self[group].add(Requirement.coerce(requirement))
        self.filename = filename

    def save(self, filename=None):
        filename = Path(filename) if filename is not None else self.filename
        with filename.open("w") as f:
            f.write(self.yaml)

    @property
    def serialized(self):
        return {group: list(map(str, requirements))
                for group, requirements in self.items()}

    @property
    def yaml(self):
        return yaml.dump(self.serialized, default_flow_style=False,
                         encoding=None)

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        else:
            ret = self[key] = self.default_factory(name=key)
            return ret


class Bower(object):
    bower_base_uri = "https://bower.herokuapp.com"

    @classmethod
    def get_package_url(cls, package, session=None, silent=False):
        response = get("{}/packages/{}".format(cls.bower_base_uri, package))
        return response.json().get("url", None)

    @classmethod
    def clean_semver(cls, version_spec):
        return re.sub(r"([<>=~])\s+?v?", "\\1", version_spec, re.IGNORECASE)


class Hydrogen(object):
    def __init__(self, assets_dir=None, requirements_file="requirements.yml"):
        self.assets_dir = assets_dir or Path(".") / "assets"
        self.requirements = GroupedRequirements()
        self.requirements.load(requirements_file)
        self.temp_dir = mkdtemp()

    def extract_bower_zipfile(self, zip_file, dest, expected_version=None):
        bower_json = None
        root = None
        deps_installed = []
        for info in zip_file.infolist():
            if PurePath(info.filename).name == "bower.json":
                with zip_file.open(info) as f:
                    bower_json = json.load(f)
                    root = str(PurePath(info.filename).parent)
                break
        version = bower_json["version"]
        if expected_version is not None:
            expected_version = Bower.clean_semver(expected_version)
            if not semver.match(version, expected_version):
                click.secho("error: versions do not match ({} =/= {})".format(
                    version, expected_version))
                raise InvalidPackageError
        if "dependencies" in bower_json:
            for package, version in bower_json["dependencies"].items():
                url = Bower.get_package_url(package)
                deps_installed.extend(self.get_bower_package(
                    url, dest=dest, version=version))
        ignore_patterns = list(map(GitIgnorePattern, bower_json["ignore"]))
        path_spec = PathSpec(ignore_patterns)
        namelist = [path for path in zip_file.namelist()
                    if PurePath(path).parts[0] == root]
        ignored = list(path_spec.match_files(namelist))
        for path in namelist:
            dest_path = PurePath(
                bower_json["name"],
                *PurePath(path).parts[1:])
            if (any(map(lambda p: p in ignored, PurePath(path).parents))
                    or path in ignored):
                continue
            if path.endswith("/"):
                if list(path_spec.match_files([str(dest_path)])):
                    ignored.append(PurePath(path))
                elif not (dest / dest_path).is_dir():
                    (dest / dest_path).mkdir(parents=True)
            else:
                target_path = dest / dest_path.parent / dest_path.name
                source = zip_file.open(path)
                target = target_path.open("wb")
                with source, target:
                    shutil.copyfileobj(source, target)
        deps_installed.append((bower_json["name"], bower_json["version"]))
        return deps_installed

    def get_bower_package(self, url, dest=None, version=None,
                          process_deps=True):
        dest = dest or Path(".") / "assets"
        parsed_url = urlparse(url)
        if parsed_url.scheme == "git" or parsed_url.path.endswith(".git"):
            if parsed_url.netloc == "github.com":
                user, repo = parsed_url.path[1:-4].split("/")
                response = get(github_api_uri
                               + "/repos/{}/{}/tags".format(user, repo))
                tags = response.json()
                target = None
                if not len(tags):
                    click.secho("fatal: no tags exist for {}/{}".format(
                        user, repo), fg="red")
                    raise InvalidPackageError
                if version is None:
                    target = tags[0]
                else:
                    for tag in tags:
                        if semver.match(tag["name"],
                                        Bower.clean_semver(version)):
                            target = tag
                            break
                if not target:
                    click.secho(
                        "fatal: failed to find matching tag for "
                        "{user}/{repo} {version}".format(user, repo, version),
                        fg="red")
                    raise VersionNotFoundError
                click.secho("installing {}/{}#{}".format(
                    user, repo, tags[0]["name"]), fg="green")
                return self.get_bower_package(
                    url=target["zipball_url"],
                    dest=dest,
                    version=version)
            raise NotImplementedError
            print("git clone {url} {dest}".format(url=url, dest=dest))
            click.echo("git clone {url}".format(url=url))
            cmd = envoy.run('git clone {url} "{dest}"'.format(
                url=url, dest=dest))
            print cmd.status_code, cmd.std_err
        elif parsed_url.scheme in ("http", "https"):
            zip_dest = download_file(url, dest=self.temp_dir,
                                     label="{dest_basename}",
                                     expected_extension="zip")
            with zipfile.ZipFile(zip_dest, "r") as pkg:
                return self.extract_bower_zipfile(pkg, dest,
                                                  expected_version=version)
                # pkg.extractall(str(dest))
        else:
            click.secho("protocol currently unsupported :(")
            sys.exit(1)

    def install_bower(self, package, save=True, save_dev=False):
        """Installs a bower package.

        :param save: if `True`, pins the package to the Hydrogen requirements
            YAML file.
        :param save_dev: if `True`, pins the package as a development
            dependency to the Hydrogen requirements YAML file.
        :param return: a list of tuples, containing all installed package names
            and versions, including any dependencies.
        """
        requirement = Requirement.coerce(package)
        url = Bower.get_package_url(requirement.package)
        installed = list(map(lambda name, version:
                             Requirement(name, requirement.version),
                             self.get_bower_package(url)))
        for requirement in installed:
            if save:
                self.requirements["bower"].add(requirement, replace=True)
            if save_dev:
                self.requirements["bower-dev"].add(requirement, replace=True)
            success("installed {}".format(str(requirement)))
        if save or save_dev:
            self.requirements.save()
        return installed

    def install_pip(self, package, save=True, save_dev=False):
        """Installs a pip package.

        :param save: if `True`, pins the package to the Hydrogen requirements
            YAML file.
        :param save_dev: if `True`, pins the package as a development
            dependency to the Hydrogen requirements YAML file.
        :param return: a **single** :class:`Requirement` object, representing
            the installed version of the given package.
        """
        requirement = Requirement.coerce(package)
        click.echo("pip install " + requirement.package)
        cmd = envoy.run("pip install {}".format(str(requirement)))
        if cmd.status_code == 0:
            installed_packages = get_installed_pypackages()
            package = installed_packages[requirement.package]
            requirement.version = "=={}".format(package.version)
            if save:
                self.requirements["all"].add(requirement)
            if save_dev:
                self.requirements["dev"].add(requirement)
            if save or save_dev:
                self.requirements.save()
            return requirement
        else:
            fatal(cmd.std_err)


def groups_option(f):
    new_func = click.option("-g", "--groups",
                            help="Comma-separated list of requirement groups "
                            "to include.")(f)
    return update_wrapper(new_func, f)


@click.group()
@click.version_option(prog_name=prog_name)
@click.pass_context
def main(ctx):
    which = "where" if sys.platform == "win32" else "which"
    if envoy.run(which + " git").status_code != 0:
        click.secho("fatal: git not found in PATH", fg="red")
        sys.exit(1)
    ctx.obj = Hydrogen()


@main.command()
@click.pass_obj
@click.option("output_yaml", "--yaml", "-y", is_flag=True,
              help="Show requirements in YAML format.")
@click.option("--resolve", "-r", is_flag=True,
              help="Resolve version numbers for ambiguous packages.")
@groups_option
def freeze(h, output_yaml, resolve, groups):
    """Output installed packages."""
    if not groups:
        groups = filter(lambda group: not group.lower().startswith("bower"),
                        h.requirements.keys())
    else:
        groups = list(map(text_type.strip, groups.split(",")))
    if output_yaml:
        for requirements in h.requirements.values():
            for requirement in requirements:
                if resolve and not requirement.version:
                    requirement.load_installed_version()
        click.echo(h.requirements.yaml)
    else:
        for group in groups:
            if not h.requirements[group]:
                continue
            click.echo("# {}".format(group))
            for requirement in h.requirements[group]:
                if resolve and not requirement.version:
                    requirement.load_installed_version()
                click.echo(str(requirement))


@main.command()
@click.pass_obj
@click.option("--pip/--bower", default=True)
@groups_option
@click.option("--save", is_flag=True)
@click.option("--save-dev", is_flag=True)
@click.argument("packages", nargs=-1)
def install(h, pip, groups, save, save_dev, packages):
    """Install a pip or bower package."""
    groups = list(map(text_type.strip, groups.split(","))
                  if groups else h.requirements.keys())
    if not packages:
        for group in groups:
            if group not in h.requirements:
                warning("{} not in requirements".format(group))
                continue
            install = (h.install_bower if group.startswith("bower")
                       else h.install_pip)
            for requirement in h.requirements[group]:
                install(str(requirement), save=False, save_dev=False)
    if pip:
        for package in packages:
            h.install_pip(package, save=save, save_dev=save_dev)
    else:
        for package in packages:
            h.install_bower(package, save=save, save_dev=save_dev)


if __name__ == "__main__":
    main()
