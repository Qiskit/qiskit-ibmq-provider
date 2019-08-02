#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""This script converts Marshmallow schema(s) to JSON schema(s)."""

import argparse
import json
import logging
import os
import sys
from inspect import getmembers, isclass

import marshmallow
from marshmallow_jsonschema import JSONSchema

# Name of a directory to be created where generated JSON schemas will be placed
TARGET_DIR_NAME = 'generated_json_schemas'


class PathAction(argparse.Action):
    """Validates passed path to a python file (or a directory containing python files)"""

    def __call__(self, parser, namespace, path, option_string=None):
        path = os.path.normpath(path)
        path = os.path.abspath(path)
        if not os.access(path, os.R_OK):
            raise argparse.ArgumentTypeError(
                "'{0}' is not a readable path".format(path))
        is_dir = True
        if os.path.isdir(path):
            setattr(namespace, self.dest, (path, is_dir))
        else:
            setattr(namespace, self.dest, (path, not is_dir))


def traverse_dir_at(dir_path, target_schema=None):
    """ Traverses through python files at a given directory path,
        and calls find_schemas_at method on them.

    Args:
        dir_path (str): path to a directory potentially containing python files
        target_schema (str): schema class that needs to be found in one of the python files

    Returns:
         list[class]: marshmallow schema classes
    """
    marshmallow_schemas = []
    for _, _, file_list in os.walk(dir_path):
        for file in file_list:
            ext = os.path.splitext(file)[1]
            if ext == '.py':
                file_abs_path = os.path.join(dir_path, file)
                try:
                    marshmallow_schemas.extend(find_schemas_at(file_abs_path, target_schema))
                    if marshmallow_schemas and target_schema:
                        # target_schema was found since marshmallow_schemas is not empty
                        return marshmallow_schemas
                except LookupError as error:
                    logging.warning(error)
    return marshmallow_schemas


def find_schemas_at(python_file_path, target_schema=None):
    """ Tries to import a python file at a given path, traverse through its enclosed classes
        checking whether they are subclasses of marshmallow.Schema, and append matched classes to
        marshmallow_schemas collection

        Args:
            python_file_path (str): path to a target python file
            target_schema (str): schema class that needs to be found in the python file

        Returns:
             list[class]: marshmallow schema classes

        Raises:
            LookupError: when no marshmallow schemas was found in a given python file
        """
    marshmallow_schemas = []
    basename = os.path.basename(python_file_path)
    to_import = os.path.splitext(basename)[0]
    to_add = os.path.dirname(python_file_path)
    if to_add not in sys.path:
        sys.path.append(to_add)

    try:
        module = __import__(to_import)
    except ImportError as error:
        logging.warning("Could not import the following module '%s' at path '%s': %s",
                        to_import, python_file_path, error)
        return marshmallow_schemas

    for schema_name, schema_class in getmembers(module, isclass):
        is_schema = issubclass(schema_class, marshmallow.Schema)
        is_from_current_module = getattr(schema_class, '__module__') == module.__name__
        if is_schema and is_from_current_module:
            if not target_schema:
                marshmallow_schemas.append(schema_class)
            elif target_schema == schema_name:
                marshmallow_schemas.append(schema_class)
                break

    if not marshmallow_schemas:
        raise LookupError("Could not find any Marshmallow schemas under module '%s' at path '%s'" %
                          (to_import, python_file_path))
    return marshmallow_schemas


def generate_json_schemas(marshmallow_schemas, to_indent=None):
    """ Uses marshmallow-jsonschema package to generate JSON schemas from Marshmallow schemas,
        and stores them in generated_json_schemas dict as {schema_name: resulting_json_schema}.

            Args:
                marshmallow_schemas (list[class]): marshmallow schema classes
                to_indent (bool): flag that determines indentation of generated JSON schemas

            Returns:
                 dict: generated json schemas as {schema_name: resulting_json_schema}
    """
    indent = 4 if to_indent else None
    generated_json_schemas = {}
    for schema in marshmallow_schemas:
        schema_name = schema.__name__
        dumped_data = JSONSchema().dump(schema()).data
        json_schema_dict = dumped_data['definitions'][schema_name]
        json_schema_str = json.dumps(json_schema_dict,
                                     default=lambda o: '<not serializable>', indent=indent)
        generated_json_schemas[schema_name] = json_schema_str
    return generated_json_schemas


def print_json_schemas(json_schemas):
    """ Print json_schemas dict to STDOUT.

        Args:
            json_schemas dict{str: string}: json schemas as {schema_name: resulting_json_schema}
    """
    for schema_name, json_schema in json_schemas.items():
        print("{}.json: \n"
              "{}\n".format(schema_name, json_schema))


def dump_json_schemas(json_schemas):
    """ Dumps generated json schemas under ${PWD}/TARGET_DIR_NAME directory.

        Args:
            json_schemas dict{str: string}: json schemas as {schema_name: resulting_json_schema}
    """
    current_dir = os.path.abspath(os.curdir)
    target_dir = os.path.join(current_dir, TARGET_DIR_NAME)
    os.mkdir(target_dir)
    for schema_name, json_schema in json_schemas.items():
        file_name = schema_name + '.json'
        target_dest = os.path.join(target_dir, file_name)
        with open(target_dest, 'w') as out:
            out.write(json_schema)


def main():
    """ Entry method """
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s')

    parser = argparse.ArgumentParser(
        description="This script converts Marshmallow schema(s) "
                    "to JSON schema(s). It accepts a full path to a python file "
                    "that contains Marshmallow schema(s), and generates JSON schema files.",
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("--schema", required=False, type=str,
                        help="Name of a specific Marshmallow schema to be converted")

    parser.add_argument("-p", required=False, action="store_true",
                        help="FLAG: Print resulting JSON schema(s) to STDOUT "
                             "instead of generating the files")
    parser.add_argument("-i", required=False, action="store_true",
                        help="FLAG: Indent resulting JSON schema(s)")
    # Required arguments
    parser.add_argument("path", action=PathAction,
                        help="Path to a python file containing at least one Marshmallow schema "
                             "OR Path to a directory that contains python files with "
                             "at least one Marshmallow schema""")

    args = parser.parse_args()

    # Extracting Arguments
    (path, is_dir) = args.path
    target_schema = args.schema

    # Flags
    to_print = args.p
    to_indent = args.i

    if not is_dir:
        marshmallow_schemas = find_schemas_at(path, target_schema)
    else:
        marshmallow_schemas = traverse_dir_at(path, target_schema)

    json_schemas = generate_json_schemas(marshmallow_schemas, to_indent)
    if to_print:
        print_json_schemas(json_schemas)
    else:
        dump_json_schemas(json_schemas)


if __name__ == "__main__":
    main()
