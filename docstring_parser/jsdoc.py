"""JavaScript docstring parsing."""
import inspect
import re
import typing as T

from docstring_parser.common import (  # RenderingStyle,
    DEPRECATION_KEYWORDS,
    PARAM_KEYWORDS,
    RAISES_KEYWORDS,
    RETURNS_KEYWORDS,
    YIELDS_KEYWORDS,
    Docstring,
    DocstringDeprecated,
    DocstringMeta,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringStyle,
    ParseError,
)


def _build_meta(args: T.List[str], desc: str) -> DocstringMeta:
    """Build docstring element.

    :param text: docstring element text
    :param title: title of section containing element
    :return:
    """
    key = args[0]

    if key in PARAM_KEYWORDS:
        if len(args) == 3:
            key, _arg_name = args[0], args[1:]
        elif len(args) == 2:
            key, _arg_name = args[0], args[1]
        else:
            raise ParseError(
                f"Expected two or three arguments for a {key} keyword."
            )

        is_optional = None
        default = None
        type_name = None
        for name in _arg_name:
            type_match = re.search(r"\{.*?\}", name)  # type
            name_match = re.match(r"\[.*?\]", name)  # arg name
            if type_match:
                type_name = (type_match.group())
                if type_name.startswith("{"):
                    type_name = type_name[1:]
                if type_name.endswith("}"):
                    type_name = type_name[:-1]
                if type_name.endswith("="):
                    is_optional = True
                    type_name = type_name[:-1]
                continue

            elif name_match:
                arg_name = (name_match.group())
                if type_name.startswith("["):
                    type_name = type_name[1:]
                if type_name.endswith("]"):
                    type_name = type_name[:-1]
                if "=" in arg_name:
                    arg_name, default = arg_name.split("=")
                is_optional = True

            else:
                arg_name = name

        return DocstringParam(
            args=args,
            description=desc,
            arg_name=arg_name,
            type_name=type_name,
            is_optional=is_optional,
            default=default,
        )

    if key in RETURNS_KEYWORDS | YIELDS_KEYWORDS:
        type_name = None
        for name in args[1:]:
            match = re.match(r"\{.*?\}", name)
            if match:
                type_name = match.group()
                
                if type_name.startswith("{"):
                    type_name = type_name[1:]
                if type_name.endswith("}"):
                    type_name = type_name[:-1]

        return DocstringReturns(
            args=args,
            description=desc,
            type_name=type_name,
            is_generator=key in YIELDS_KEYWORDS,
        )

    if key in DEPRECATION_KEYWORDS:
        match = re.search(
            r"^(?P<version>v?((?:\d+)(?:\.[0-9a-z\.]+))) (?P<desc>.+)",
            desc,
            flags=re.I,
        )
        return DocstringDeprecated(
            args=args,
            version=match.group("version") if match else None,
            description=match.group("desc") if match else desc,
        )

    if key in RAISES_KEYWORDS:
        type_name = None
        for name in args[1:]:
            match = re.match(r"\{.*?\}", name)
            if match:
                type_name = match.group()
                
                if type_name.startswith("{"):
                    type_name = type_name[1:]
                if type_name.endswith("}"):
                    type_name = type_name[:-1]

        return DocstringRaises(
            args=args, description=desc, type_name=type_name
        )

    return DocstringMeta(args=args, description=desc)


def parse(text):
    """
    Parser the Javadoc docstring into its components.
    :param text: Docstring for parse
    :type text: str

    :returns: parsed docstring

    :example:
        >>> from docstring_parser import parse, DocstringStyle
        >>> text = '''
        ...     This is a function.

        ...     @param {string} n - A string param
        ...     @return {int} This return integer
        ...     @throws {IOException} On input error.
                '''
        >>> parse(text, DocstringStyle.JSDOC)
        <docstring_parser.common.Docstring object at 0xd49fc682bc40>

    """
    ret = Docstring(style=DocstringStyle.REST)
    text = inspect.cleandoc(text)

    match = re.search("^@", text, flags=re.M)
    if match:
        desc_chunk = text[: match.start()]
        meta_chunk = text[match.start() :]
    else:
        desc_chunk = text
        meta_chunk = ""

    parts = desc_chunk.split("\n", 1)
    ret.short_description = parts[0] or None
    if len(parts) > 1:
        long_desc_chunk = parts[1] or ""
        ret.blank_after_short_description = long_desc_chunk.startswith("\n")
        ret.blank_after_long_description = long_desc_chunk.endswith("\n\n")
        ret.long_description = long_desc_chunk.strip() or None

    for match in re.finditer(
        r"(^@.*?)(?=^@|\Z)", meta_chunk, flags=re.S | re.M
    ):
        chunk = match.group(0)

        try:
            splited = chunk.lstrip().split(" ", 1)
            if len(splited) == 1:  # only tag
                tag = splited[0]
                desc_chunk = ""
            else:
                tag, desc_chunk = splited
            # @tag (name) description
        except ValueError as ex:
            raise ParseError(
                f'Error parsing meta information near "{chunk}".'
            ) from ex

        tag = tag.strip("@")

        if tag in ["param", "typedef", "property"]:
            splited = desc_chunk.lstrip().strip('\n').split(" ", 2)
            if len(splited) == 3:
                _, args_chunk, desc_chunk = splited
            elif len(splited) == 2:
                _, args_chunk = splited
                desc_chunk = ""
            else:
                raise ParseError(
                    f'Expected two or three arguments for a "{tag}" keyword.'
                )

            args = [tag, _, args_chunk.strip("\n")]

        elif tag in ["return", "throws", "type"]:
            splited = desc_chunk.lstrip().split(" ", 1)
            desc_chunk = ""
            if len(splited) == 2:
                args_chunk, desc_chunk = splited
            elif len(splited) == 1:
                args_chunk = splited[0]
            else:
                raise ParseError(
                    f'Expected two arguments for a "{tag}" keyword.'
                )
            args = [tag, args_chunk]

        else:
            args = [tag.strip("\n")]

        desc = desc_chunk.strip()
        if "\n" in desc:
            first_line, rest = desc.split("\n", 1)
            desc = first_line + "\n" + inspect.cleandoc(rest)

        ret.meta.append(_build_meta(args, desc))

    # for meta in ret.meta:
    #     if isinstance(meta, DocstringParam):
    #         meta.type_name = meta.type_name or types.get(meta.arg_name)
    return ret
