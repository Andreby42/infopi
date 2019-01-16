# coding=utf-8

import threading
try:
    import regex as re
    vt = tuple(int(i.strip()) for i in re.__version__.split('.'))
    if vt < (2, 4, 105):
        print('regex版本较低:%s, 使用内置re' % re.__version__)
        raise Exception('regex version is low')
    re.DEFAULT_VERSION = re.VERSION0
except:
    import re

#========================================
#       regular expression wrapper
#========================================


class red:
    A = re.A
    ASCII = re.ASCII

    DEBUG = re.DEBUG

    I = re.I
    IGNORECASE = re.IGNORECASE

    L = re.L
    LOCALE = re.LOCALE

    M = re.M
    MULTILINE = re.MULTILINE

    S = re.S
    DOTALL = re.DOTALL

    X = re.X
    VERBOSE = re.VERBOSE

    # cache
    regexs = dict()

    # threading lock
    lock = threading.Lock()

    @staticmethod
    def d(re_str, flags=0):
        '''compiled pattern cache'''
        red.lock.acquire()

        compiled = red.regexs.get((re_str, flags), 0)
        if compiled == 0:
            try:
                compiled = re.compile(re_str, flags)
            except Exception as e:
                print('编译正则表达式时出现异常:', e)
                print('正则式:', re_str)
                print('模式:', flags, '\n')
                compiled = None
            red.regexs[(re_str, flags)] = compiled

        red.lock.release()

        return compiled

    # not applicable to the situations where need to
    # generate informative error prompt
    @staticmethod
    def sub(pattern, repl, string, count=0, flags=0):
        prog = red.d(pattern, flags)
        try:
            return prog.sub(repl, string, count=count)
        except:
            print('red.sub()函数出现异常，可能是正则表达式编译失败')
            raise

    @staticmethod
    def clear_cache():
        red.lock.acquire()
        red.regexs.clear()
        red.lock.release()
