#!/usr/bin/env python3

# Copyright or © or Copr. Guillaume Lemaître (2013)
#
# guillaume.lemaitre@gmail.com
#
# This software is a computer program whose purpose is to help management
# of requirements'documentation with any SCM.
#
# This software is governed by the CeCILL license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".
#
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.
#
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.
#
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL license and that you accept its terms.

"""Requirement Management with any SCM

When editing a document, it is best seen as a whole, in a single file. But,
when stored, in order to verify its evolution, it is best seen split, a
requirement per file. Finally, when published, additional formatting is
required on edition form. RMS provides the minimum functionnalities to go from
one view to another, and thus edit efficiently a requirements'document.
"""

import collections
import hashlib
import io
import logging
import re
import sys


# Configurable input/output features
REQUIREMENT_TAG = "RMS-REQ"
REQUIREMENT_INC = "RMS-INC"
REQUIREMENT_MEM = "RMS-MEM"

IDENTIFIER_REGEX = "^[0-9A-Za-z-]+$"
FORMAT_HEADER = "SPEC-REQ-"
N = 3

PUBLISH_FORMAT = """**[{req_id}]**

{req_content}

**-- End of requirement**
"""

# Intermediate 'command' type
Command = collections.namedtuple("Command", ["function", "input_file"])


##############################################################################
# 'merge' command implementation
##############################################################################

def merge(input_file):
    used_ids = set()

    with open(input_file, "rt") as text:
        for line in text:
            if line.startswith(REQUIREMENT_INC):
                req_id = line[len(REQUIREMENT_INC) + 1:-1]
                used_ids.add(req_id)

                sys.stdout.write("{} {}\n".format(REQUIREMENT_TAG, req_id))
                with open(req_id + ".rms", "rt") as req:
                    for line_req in req:
                        sys.stdout.write(line_req)
                sys.stdout.write("-- {}\n".format(REQUIREMENT_TAG))

            elif line.startswith(REQUIREMENT_MEM):
                req_id = line[len(REQUIREMENT_MEM) + 1:-1]
                used_ids.add(req_id)

            else:
                sys.stdout.write(line)

        # Keep track of all requirements ids, in case some of them disappear
        # during editing
        for req_id in sorted(used_ids):
            sys.stdout.write("{} {}\n".format(REQUIREMENT_MEM, req_id))


##############################################################################
# 'split' command implementation
##############################################################################

def split(input_file):
    cited_ids = set()

    # Parse file in order to collect already used requirement identifiers
    used_ids = _collect_ids(input_file)

    # Actually split the file
    output = sys.stdout

    with open(input_file, "rt") as text:
        line_num = 1
        for line in text:
            if line.startswith(REQUIREMENT_TAG):
                req_id = _isolate_id(line, line_num)
                output = io.StringIO()

            elif line.startswith("-- " + REQUIREMENT_TAG):
                output.seek(0)
                content = output.read()

                if req_id is None:
                    req_id = _reserve_id_hash(used_ids, content)
                cited_ids.add(req_id)

                output_file = open(req_id + ".rms", "wt")
                output_file.write(content)
                output_file.close()

                output = sys.stdout
                output.write("{} {}\n".format(REQUIREMENT_INC, req_id))

            elif not line.startswith(REQUIREMENT_MEM):
                output.write(line)

            line_num += 1

        # Keep memory only of unused requirement identifiers
        for req_id in sorted(used_ids.difference(cited_ids)):
            output.write("{} {}\n".format(REQUIREMENT_MEM, req_id))


def _collect_ids(input_file):
    result = set()

    line_num = 0
    with open(input_file, "rt") as text:
        for line in text:
            line_num += 1
            if line.startswith(REQUIREMENT_MEM):
                req_id = line[len(REQUIREMENT_MEM) + 1:-1]
                result.add(req_id)

            elif line.startswith(REQUIREMENT_TAG):
                req_id = _isolate_id(line, line_num)
                if req_id in result:
                    logging.error(
                        "line {}: '{}' identifier is not unique".format(
                            line_num, result))
                elif req_id is not None:
                    result.add(req_id)

    return result


def _isolate_id(line, line_num):
    result = line[len(REQUIREMENT_TAG):].strip()

    if len(result) == 0:
        result = None
    elif not re.match(IDENTIFIER_REGEX, result):
        logging.error("line {}: '{}' identifier is ill formed".format(
                line_num, result))
        result = None

    return result


def _reserve_id_cont(used_ids, content):
    max_n = -1
    for used_id in used_ids:
        if used_id.startswith(FORMAT_HEADER):
            n = used_id[len(FORMAT_HEADER):]
            if n.isdigit():
                n = int(n)
                max_n = max(n, max_n)

    max_n += 1
    result = FORMAT_HEADER + ("{:0>" + str(N) + "d}").format(max_n)
    used_ids.add(result)

    return result


def _reserve_id_hash(used_ids, content):
    hashing = hashlib.md5()
    hashing.update(content.encode("utf-8"))
    footprint = str(int(hashing.hexdigest(), 16))[::-1]

    # First try: only the first N characters
    result = FORMAT_HEADER + footprint[:N]
    if result not in used_ids:
        used_ids.add(result)

    # Second try: extract as short prefix as possible
    else:
        footprint = footprint.strip("0")
        for n in range(N, len(footprint) + 1):
            result = FORMAT_HEADER + footprint[:n]
            if result not in used_ids:
                used_ids.add(result)
                break
        else:
            logging.error("Cannot generate a new unique identifier")
            result = None

    return result


##############################################################################
# 'usage' command implementation
##############################################################################

def usage(input_file):
    print("""
Usage: {cmd} [split|merge] FILE
       transform input FILE on standard output

$> {cmd} split FILE > FILE.out
search for each '{req}' mark and output it in a different file

$> {cmd} merge FILE > FILE.out
search for each '{inp}' mark and merge it with normal output

$> {cmd} yield FILE > FILE.out
search for each '{inp}' mark, merge and format it with normal output
""".format(cmd = input_file, req = REQUIREMENT_TAG, inp = REQUIREMENT_INC))


##############################################################################
# 'yield' command implementation
##############################################################################

def yield_cmd(input_file):
    with open(input_file, "rt") as text:
        for line in text:
            if line.startswith(REQUIREMENT_INC):
                req_id = line[len(REQUIREMENT_INC) + 1:-1]

                content = io.StringIO()
                with open(req_id + ".rms", "rt") as req:
                    for line_req in req:
                        content.write(line_req)

                content.seek(0)
                req_content = content.read().strip("\n")
                sys.stdout.write(PUBLISH_FORMAT.format(
                        req_id = req_id,
                        req_content = req_content))

            # Technical informations shall be removed from final document
            elif not line.startswith(REQUIREMENT_MEM):
                sys.stdout.write(line)


# Other functions

def parse(args):
    result = Command(usage, "rms")

    if len(args) == 2:
        if args[0] == "merge":
            result = Command(merge, args[1])
        elif args[0] == "split":
            result = Command(split, args[1])
        elif args[0] == "yield":
            result = Command(yield_cmd, args[1])

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    COMMAND = parse(sys.argv[1:])
    COMMAND.function(COMMAND.input_file)
