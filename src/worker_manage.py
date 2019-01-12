# coding=utf-8
import threading
import time
import datetime
import hashlib
import collections

import bvars
from datadefine import *
from red import *


def for_wz(s):
    # translate for wz_tooltip.js (web tooltip)
    return s.replace('\n', '').replace('\r', '')


# for funcs.datetime()
dt_namedtuple = collections.namedtuple('dt', ('year', 'mon', 'day',
                                              'hour', 'min', 'sec',
                                              'wday', 'yday', 'isdst'))


class Functions:
    '在callback代码里可使用的便利函数，显式抛出异常。'
    __slots__ = ()

    def __setattr__(self, name, value):
        raise Exception('给funcs.%s的赋值无效，funcs是只读对象。' % name)

    def __getattribute__(self, name):
        if name[:2] == '__':
            raise Exception('请勿访问funcs对象的系统变量: %s' % name)

        try:
            return Functions.__dict__[name].__func__
        except:
            raise Exception('funcs对象没有这个方法: %s' % name)

    @staticmethod
    def hasher(string):
        try:
            b = string.encode('utf-8')
            h = hashlib.md5(b).hexdigest()
            return h
        except Exception as e:
            print('funcs.hasher函数异常', e)
            raise

    @staticmethod
    def unixtime(string, fmt='%m-%d %H:%M'):
        try:
            return datetime.datetime.\
                fromtimestamp(float(string)).\
                strftime(fmt)
        except Exception as e:
            print('funcs.unixtime函数异常', e)
            raise

    # add in 2017.1.15
    @staticmethod
    def resub(pattern, repl, string, count=0):
        try:
            return red.sub(pattern, repl, string, count=count)
        except Exception as e:
            print('funcs.resub函数异常', e)
            raise

    # add in 2017.1.16b
    @staticmethod
    def research(pattern, string):
        try:
            r = red.d(pattern)
            m = r.search(string)
            return m is not None
        except Exception as e:
            print('funcs.research函数异常', e)
            raise

    # add in 2017.1.25
    @staticmethod
    def datetime():
        global dt_namedtuple

        t = time.localtime()
        return dt_namedtuple(t.tm_year, t.tm_mon, t.tm_mday,
                             t.tm_hour, t.tm_min, t.tm_sec,
                             t.tm_wday + 1, t.tm_yday, t.tm_isdst)


funcs = Functions()


class c_worker_exception(Exception):

    def __init__(self, title, url='', summary=''):
        self.title = title
        self.url = url
        self.summary = summary

    def __str__(self):
        s = '异常:' + self.title + '\n'
        if self.url:
            s += self.url + '\n'
        if self.summary:
            s += self.summary + '\n'
        return s


# 启动worker线程
def worker_starter(runcfg, source_id):

    def worker_wrapper(runcfg,
                       worker, source, worker_dict,
                       back_web_queue, bb_queue,
                       cfg_token):

        # print('线程开始：%s' % source.source_id)

        int_time = int(time.time())

        try:
            # 信息源定义异常
            if worker is None:
                s = '信息源%s没有找到指定worker: %s' % \
                    (source.source_id, source.worker_id)
                print(s)
                raise c_worker_exception(s)

            if source.data is None:
                s = '信息源%s的data未能被解析' % source.source_id
                print(s)
                raise c_worker_exception(s)

            if type(source.callback) is str:
                s = '信息源%s的callback代码编译失败' % source.source_id
                print(s)
                raise c_worker_exception('编译callback代码失败', '',
                                         source.callback)

            if type(source.list_callback) is str:
                s = '信息源%s的list_callback代码编译失败' % source.source_id
                print(s)
                raise c_worker_exception('编译list_callback代码失败', '',
                                         source.list_callback)

            # run worker
            lst = worker(source.data, worker_dict)

            # max length of info list
            if source.max_len is not None:
                if len(lst) > source.max_len:
                    lst = lst[:source.max_len]
            elif len(lst) > runcfg.max_entries:
                lst = lst[:runcfg.max_entries]

            global funcs
            # callback函数
            if source.callback is not None:
                newlst = list()
                local_d = dict()

                local_d['funcs'] = funcs
                local_d['hasher'] = funcs.hasher
                local_d['unixtime'] = funcs.unixtime

                for i, info in enumerate(lst):
                    local_d['posi'] = i
                    local_d['info'] = info
                    try:
                        exec(source.callback, None, local_d)
                    except Exception as e:
                        print('callback代码运行异常:', e)
                        raise c_worker_exception('callback代码运行异常', '',
                                                 str(e))

                    if info.temp != 'del':
                        newlst.append(info)

                lst = newlst

            # list_callback函数
            if source.list_callback is not None:
                local_d = dict()

                local_d['funcs'] = funcs
                local_d['infos'] = lst

                try:
                    exec(source.list_callback, None, local_d)
                except Exception as e:
                    print('list_callback代码运行异常:', e)
                    raise c_worker_exception('list_callback代码运行异常', '',
                                             str(e))
                lst = local_d['infos']

                if not isinstance(lst, (list, tuple)):
                    raise c_worker_exception('list_callback的返回类型应为list',
                                             '',
                                             '实际返回类型:%s' % str(type(lst)))

                for i in lst:
                    if not isinstance(i, c_info):
                        raise c_worker_exception(
                            'list_callback返回的列表元素不是一条信息(c_info)',
                            '',
                            '实际元素类型:%s' % str(type(i)))

            # remove duplicate suid, only keep the first one
            # (escape special suid inside this code)
            suid_set = set()
            newlst = list()
            for one in lst:
                # escape special suid
                if one.suid == '<exception>':
                    one.suid = '#<exception>#'

                if one.suid not in suid_set:
                    suid_set.add(one.suid)
                    newlst.append(one)

            lst = newlst

        except c_worker_exception as e:
            s = '\n源%s出现worker异常:' % source.source_id
            print(s, e)

            i = c_info()
            i.title = '异常:' + e.title
            try:
                i.url = e.url or str(source.data.get('url', ''))
            except:
                pass
            i.summary = e.summary
            i.suid = '<exception>'

            lst = [i]

            is_exception = True

        except Exception as e:
            print('执行worker时程序异常:', e)

            i = c_info()
            i.title = '程序出现异常'
            i.summary = str(e)
            i.suid = '<exception>'

            lst = [i]

            is_exception = True

        else:
            is_exception = False

        finally:
            # 通知执行结束
            c_message.make(bb_queue,
                           'bb:source_return',
                           cfg_token,
                           source.source_id
                           )

            if not lst:
                print('%s获得的列表为空' % source.source_id)

            # 处理内容
            for i in lst:
                i.source_id = source.source_id

                if not i.title:
                    i.title = '<title>'

                if not i.author:
                    i.author = source.name

                i.fetch_date = int_time

                if not i.suid:
                    print(i.source_id, '出现suid为空')

                # length
                if len(i.title) > runcfg.title_len:
                    i.title = i.title[:runcfg.title_len - 3] + '...'

                if len(i.summary) > runcfg.summary_len:
                    i.summary = i.summary[:runcfg.summary_len - 3] + '...'

                if len(i.author) > runcfg.author_len:
                    i.author = i.author[:runcfg.author_len - 3] + '...'

                if len(i.pub_date) > runcfg.pub_date_len:
                    i.pub_date = i.pub_date[:runcfg.pub_date_len - 3] + '...'

                # for tooltip show
                global for_wz
                i.summary = for_wz(i.summary)
                i.pub_date = for_wz(i.pub_date)

            if is_exception:
                c_message.make(back_web_queue,
                               'bw:exception_info',
                               cfg_token,
                               lst)
            else:
                fetch_date_str = datetime.datetime.\
                    fromtimestamp(int_time).\
                    strftime('%m-%d %H:%M')
                data = [source.source_id, fetch_date_str, lst]
                c_message.make(back_web_queue,
                               'bw:success_infos',
                               cfg_token,
                               data)

        # print('线程结束：%s' % source.source_id)

    source = bvars.sources[source_id]

    try:
        worker_tuple = bvars.workers[source.worker_id]
    except:
        worker = None
        worker_dict = None
    else:
        worker = worker_tuple[0]
        worker_dict = worker_tuple[1]

    t = threading.Thread(target=worker_wrapper,
                         args=(runcfg,
                               worker,
                               source, worker_dict,
                               bvars.back_web_queue, bvars.bb_queue,
                               bvars.cfg_token),
                         daemon=True
                         )
    t.start()


# for test source
def test_source(source_id):
    source = bvars.sources[source_id]

    try:
        worker_tuple = bvars.workers[source.worker_id]
    except:
        print('信息源%s没有找到指定worker: %s' %
              (source.source_id, source.worker_id)
              )
        return

    worker = worker_tuple[0]
    worker_dict = worker_tuple[1]

    int_time = int(time.time())

    # run
    try:
        if source.data is None:
            raise Exception('信息源%s的data未能被解析' % source.source_id)

        lst = worker(source.data, worker_dict)

    except Exception as e:
        print('\n    源%s出现异常:\n' % source.source_id)

        raise e

    else:
        # max length of info list
        if source.max_len is not None:
            if len(lst) > source.max_len:
                lst = lst[:source.max_len]

        global funcs
        # callback函数
        if source.callback is not None:
            newlst = list()
            local_d = dict()

            local_d['funcs'] = funcs
            local_d['hasher'] = funcs.hasher
            local_d['unixtime'] = funcs.unixtime

            for i, info in enumerate(lst):
                local_d['posi'] = i
                local_d['info'] = info
                try:
                    exec(source.callback, None, local_d)
                except Exception as e:
                    print('callback异常:', e)
                    info.title = 'callback代码异常'
                    info.summary = str(e)

                if info.temp != 'del':
                    newlst.append(info)

            lst = newlst

        # list_callback函数
        if source.list_callback is not None:
            local_d = dict()

            local_d['funcs'] = funcs
            local_d['infos'] = lst

            try:
                exec(source.list_callback, None, local_d)
                lst = local_d['infos']

                if not isinstance(lst, (list, tuple)):
                    raise Exception('infos的类型应为list')

                for i in lst:
                    if not isinstance(i, c_info):
                        raise Exception('列表的元素不是一条信息(c_info)')
            except Exception as e:
                print('list_callback异常:', e)
                print()
                raise

        for i in lst:
            i.source_id = source.source_id
            if not i.author:
                i.author = source.name
            i.fetch_date = int_time

            if not i.suid:
                print(i.source_id, '出现suid为空')

            if len(i.title) > 70:
                i.title = i.title[:67] + '...'

            if len(i.summary) > 160:
                i.summary = i.summary[:157] + '...'

            if len(i.author) > 50:
                i.author = i.author[:47] + '...'

            if len(i.pub_date) > 50:
                i.pub_date = i.pub_date[:47] + '...'

        print('\n---------- 以下为测试结果 ----------')
        print(' 信息源id(source_id)为 %s' % source.source_id)
        print(' 获取了%d条信息\n' % len(lst))

        if len(lst) > 16:
            print_str = ''.join(str(i) for i in lst[:8]) + \
                        '...中间省略%d条...\n\n' % (len(lst) - 16) + \
                        ''.join(str(i) for i in lst[-8:])
        else:
            print_str = ''.join(str(i) for i in lst)

        try:
            print(print_str)
        except UnicodeEncodeError:
            temp = str(print_str)
            for t in temp:
                try:
                    print(t, end='')
                except:
                    print('?', end='')
            print()


# parse source data, return a dict or raise
def parse_data(worker_id, xml_string):
    try:
        parser = bvars.dataparsers[worker_id]
    except:
        # can't find the data-parser, maybe the worker doesn't need data.
        # if worker_id doesn't exist, worker_starter will catch the issue.
        return dict()

    # caller should catch exception for this
    return parser(xml_string)

# worker function:
# params: (data_dict, worker_dict)
# return: list(info) or c_worker_exception

# worker decorator


def worker(worker_id):

    def worker_decorator(func):
        if worker_id not in bvars.workers:
            bvars.workers[worker_id] = (func, dict())
        else:
            print('警告: 出现重复的<worker函数>，请检查src/workers目录下的程序。')
            print('重复的<worker函数>为%s，由@worker装饰。' % worker_id)
        return func

    return worker_decorator

# dataparser function:
# params: (xml_string)
# return: data_dict

# data-parser decorator


def dataparser(worker_id):

    def dataparser_decorator(func):
        if worker_id not in bvars.dataparsers:
            bvars.dataparsers[worker_id] = func
        else:
            print('警告: 出现重复的<worker解析器>，请检查src/workers目录下的程序。')
            print('重复的<worker解析器>为%s，由@dataparser装饰。' % worker_id)
        return func

    return dataparser_decorator
