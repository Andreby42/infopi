# coding=utf-8

import os
import copy
import codecs
import xml.etree.ElementTree as ET

import bvars

from worker_manage import parse_data

__all__ = ('load_sources')

sources = bvars.sources


class c_source:
    __slots__ = ('source_id',
                 'name', 'comment', 'link',
                 'worker_id', 'data',
                 'callback', 'list_callback',
                 'xml',
                 'max_len', 'max_db')

    def __init__(self):
        self.source_id = ''

        self.name = ''
        self.comment = ''
        self.link = ''

        self.worker_id = ''
        self.data = None

        self.callback = None
        self.list_callback = None

        self.xml = ''

        self.max_len = None
        self.max_db = None


temp_dict = None


def load_xml(sources_path, path, filename, test_sid):
    def get_text_from_tag(tag):
        if tag is not None:
            return tag.text.strip()
        else:
            return ''

    global temp_dict

    full_path = os.path.join(sources_path, path, filename)

    # load file
    try:
        f = open(full_path, 'rb')
        byte_data = f.read()
        f.close()
    except Exception as e:
        print('读取文件%s:%s时出错' % (path, filename), str(e))
        return

    # decode
    try:
        if byte_data[:3] == codecs.BOM_UTF8:
            byte_data = byte_data[3:]

        string = byte_data.decode('utf-8')
    except Exception as e:
        print('文件%s:%s解码失败，请确保是utf-8编码。' % (path, filename),
              '(有没有BOM无所谓)\n', str(e), '\n')
        return

    # lower and remove '.xml'
    lpath = path.lower()
    lfilename = filename.lower()

    if len(lfilename) < 5 or lfilename[-4:] != '.xml':
        return

    short_fn = lfilename[:-4]

    # windows不区分大小写，不必提示
    if short_fn in temp_dict:
        # print('提示:\n%s:%s已存在，本程序不区分大小写' % (lpath, short_fn))
        return

    # get xml object
    try:
        xml = ET.fromstring(string)
    except Exception as e:
        s = ('解析信息源XML文件失败,请检查XML的格式 %s:%s\n'
             '异常:%s\n'
             '如果XML中出现如下字符，请转义替换:\n'
             '  &替换成&amp;\n'
             '  <替换成&lt;\n'
             '  >替换成&gt;\n'
             '请搜索以下关键字了解详情：xml 实体 转义\n'
             )
        print(s % (lpath, lfilename, str(e)))
        return

    # load father first
    father = xml.attrib.get('father', '')
    if father and father not in temp_dict:
        load_xml(sources_path, path, father + '.xml', test_sid)

    # make source object
    s = c_source()
    s.source_id = lpath + ':' + short_fn

    s.name = get_text_from_tag(xml.find('name'))
    s.comment = get_text_from_tag(xml.find('comment'))
    s.link = get_text_from_tag(xml.find('link'))

    # worker may be '', judge it later
    s.worker_id = get_text_from_tag(xml.find('worker'))

    callback = get_text_from_tag(xml.find('callback'))
    if callback != '':
        try:
            s.callback = compile(callback, '<string>', 'exec')
        except:
            print('编译信息源%s的callback代码失败' % s.source_id)
            raise

    list_callback = get_text_from_tag(xml.find('list_callback'))
    if list_callback != '':
        s.list_callback = compile(list_callback, '<string>', 'exec')

    def common_procedure(s, string):
        if s.worker_id == '':
            raise Exception('信息源错误：worker为空')

        # parse data
        try:
            s.data = parse_data(s.worker_id, string)
        except:
            print('解析信息源%s的data失败' % s.source_id)
            raise

    # use father data
    if father:
        father_s = temp_dict[father]

        # worker
        s.worker_id = s.worker_id or father_s.worker_id

        # judge worker, parse
        common_procedure(s, string)

        # data
        father_data = copy.deepcopy(father_s.data)
        father_data.update(s.data)
        s.data = father_data

        # callback
        if s.callback is None:
            s.callback = father_s.callback

        if s.list_callback is None:
            s.list_callback = father_s.list_callback

        # father + xml
        s.xml = father_s.xml + string

        s.max_len = father_s.max_len
        s.max_db = father_s.max_db
    else:
        # judge worker, parse
        common_procedure(s, string)

        # xml content
        s.xml = string

    # max_len
    max_len = get_text_from_tag(xml.find('max_len'))
    if max_len != '':
        try:
            max_len = int(max_len)
            if max_len > 0:
                s.max_len = max_len
            else:
                print('信息源%s的max_len应>0，忽略: %d' % (s.source_id, max_len))
        except:
            print('信息源%s的max_len有误，忽略: %s' % (s.source_id, max_len))

    # max_db
    max_db = get_text_from_tag(xml.find('max_db'))
    if max_db != '':
        try:
            max_db = int(max_db)
            if max_db > 1:
                s.max_db = max_db
            else:
                print('信息源%s的max_db应>1，忽略: %d' % (s.source_id, max_db))
        except:
            print('信息源%s的max_db有误，忽略: %s' % (s.source_id, max_db))

    # print max_len and max_db
    if test_sid == s.source_id:
        if s.max_len is not None:
            print('信息源%s的max_len被设为%d' % (s.source_id, s.max_len))
        if s.max_db is not None:
            print('信息源%s的max_db被设为%d' % (s.source_id, s.max_db))

    # add to dict
    temp_dict[short_fn] = s
    sources[s.source_id] = s


def load_sources(test_sid=None):
    if test_sid is not None:
        test_sid = test_sid.lower()

    # clear first
    sources.clear()

    # sources_path
    sources_path = os.path.join(bvars.root_path, 'cfg')

    # for load father data
    global temp_dict
    temp_dict = dict()

    # load files
    for l1_item in os.listdir(sources_path):
        l1_path = os.path.join(sources_path, l1_item)
        temp_dict.clear()

        if os.path.isdir(l1_path):
            for l2_item in os.listdir(l1_path):
                l2_path = os.path.join(l1_path, l2_item)
                if os.path.isfile(l2_path):
                    try:
                        load_xml(sources_path, l1_item, l2_item,
                                 test_sid)
                    except:
                        pass

    print('back-side loaded %d sources' % len(sources))

    del temp_dict
