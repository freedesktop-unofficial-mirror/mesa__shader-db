#!/usr/bin/env python3

import re
import sys
import os
import time
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import cpu_count


def process_directories(items):
    for item in items:
        if os.path.isfile(item):
            yield item
        else:
            for dirpath, _, filenames in os.walk(item):
                for fname in filenames:
                    if os.path.splitext(fname)[1] == '.shader_test':
                        yield os.path.join(dirpath, fname)


def run_test(filename):
    if ".out" in filename:
        return ""

    timebefore = time.time()

    try:
        p = subprocess.Popen(
            ['./bin/shader_runner', filename, '-auto', '-fbo'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate()
        results = (stdout + stderr).decode("utf-8")
    except KeyboardInterrupt:
        exit(1)
    except:
        return filename + " FAIL\n"

    timeafter = time.time()

    with open(filename + '.out', 'w') as file:
        file.write(results)

    counts = {}

    lines = (line for line in results.splitlines())
    re_number = re.compile(
        r'Native code for (unnamed )?(fragment|vertex|geometry) (shader|program) (?P<number>\d+)')
    for line in lines:
        shader = re_number.match(line)
        if shader and int(shader.group('number')) > 0:
            break
    else:
        raise Exception('Only shader 0 found. {}'.format(filename))

    re_search = re.compile(
        r'(?P<stage>[A-Za-z0-9]+) (vec4 )?shader\: (?P<count>\d+) instructions.')
    for line in lines:
        match = re_search.match(line)
        if match is not None:
            counts[match.group('stage')] = int(match.group('count'))

    assert counts, 'File: {} does not have any shaders'.format(filename)

    timestr = "    {:.3f} secs".format(timeafter - timebefore)
    out = ''
    for k, v in counts.items():
        if v != 0:
            out += "{0:40} {1} : {2:6}{3}\n".format(filename, k, v, timestr)
            timestr = ""
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("shader",
                        nargs='*',
                        default=['shaders'],
                        metavar="<shader_file | shader dir>",
                        help="A shader file or directory containing shader "
                             "files. Defaults to 'shaders/'")
    args = parser.parse_args()

    os.environ["shader_precompile"] = "true"
    os.environ["allow_glsl_extension_directive_midshader"] = "true"
    if "INTEL_DEBUG" in os.environ:
        print("Warning: INTEL_DEBUG environment variable set!", file=sys.stderr)
        os.environ["INTEL_DEBUG"] += ",vs,gs,fs"
    else:
        os.environ["INTEL_DEBUG"] = "vs,gs,fs"

    try:
        os.stat("bin/glslparsertest")
    except OSError:
        print("./bin must be a symlink to a built piglit bin directory")
        sys.exit(1)

    runtimebefore = time.time()

    filenames = process_directories(args.shader)

    executor = ThreadPoolExecutor(cpu_count())
    for t in executor.map(run_test, filenames):
        sys.stdout.write(t)

    runtime = time.time() - runtimebefore
    print("shader-db run completed in {:.1f} secs".format(runtime))


if __name__ == "__main__":
    main()
