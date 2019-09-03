# coding=utf-8

import datetime
import time
import os
import queue
from zipfile import ZipFile, is_zipfile
import shutil
from enum import IntEnum

try:
    import winsound
except:
    winsound = None

# ---------------------

from flask import (Flask, render_template, request,
                   make_response, redirect,
                   send_from_directory)

# ---------------------

import wvars
from db_wrapper import *
from datadefine import *
from rpi_stat import *

web = Flask(__name__,
            static_folder=wvars.static_folder,
            template_folder=wvars.template_folder)

web_back_queue = None
back_web_queue = None

gcfg = None
db = None

template_cache = dict()

# 在此源文件中，pad实际指大屏手机版，pad2实际指pad版


class PG_TYPE(IntEnum):
    GATHER = 0
    CATEGORY = 1
    SOURCE = 2
    M_GATHER = 3
    M_CATEGORY = 4
    M_EXCEPTION = 5
    BM_GATHER = 6
    BM_CATEGORY = 7
    BM_EXCEPTION = 8
    P2_GATHER = 9
    P2_CATEGORY = 10
    P2_EXCEPTION = 11


class DV_TYPE(IntEnum):
    COMPUTER = 0
    PAD = 1
    MOBILE = 2
    BIGMOBILE = 3

wrong_key_html = ('在当前的用户配置中，没有找到这个版块。<br>'
                  '请刷新 整个页面（或上一级目录页面），以得到最新的版块目录。')

zero_user_loaded = ('尚未载入任何用户，请在3秒后刷新此页面。<br>'
                    '如问题依旧，请检查用户配置、后端进程的状态。'
                    )

jump_to_login = r'<script>top.location.href="/login";</script>'

user_type_str = ('公共账号', '普通账号', '管理员')

#-------------------------------
#         page part
#-------------------------------

# page nag part


def generate_page(all_count, now_pg,
                  col_per_page,
                  p_type, category):

    def make_pattern(p_type, category):
        # computer
        if p_type == PG_TYPE.GATHER:
            template_tuple = ('<a href="/list', str(category),
                              '/%d">%s</a>')
        elif p_type == PG_TYPE.CATEGORY:
            template_tuple = ('<a href="/list/', category,
                              '/%d">%s</a>')
        elif p_type == PG_TYPE.SOURCE:
            template_tuple = ('<a href="/slist', category,
                              '/%d">%s</a>')
        # mobile
        elif p_type == PG_TYPE.M_GATHER:
            template_tuple = ('<a href="/ml', str(category),
                              '/%d">%s</a>')
        elif p_type == PG_TYPE.M_CATEGORY:
            template_tuple = ('<a href="/ml/', category,
                              '/%d">%s</a>')
        # pad
        elif p_type == PG_TYPE.P2_GATHER:
            template_tuple = ('<a href="/pad', str(category),
                              '/%d#bd">%s</a>')
        elif p_type == PG_TYPE.P2_CATEGORY:
            template_tuple = ('<a href="/pad/', category,
                              '/%d#bd">%s</a>')

        # big mobile
        elif p_type == PG_TYPE.BM_GATHER:
            template_tuple = ('<a href="/plist', str(category),
                              '/%d">%s</a>')
        elif p_type == PG_TYPE.BM_CATEGORY:
            template_tuple = ('<a href="/plist/', category,
                              '/%d">%s</a>')

        # exceptions
        elif p_type == PG_TYPE.M_EXCEPTION:
            template_tuple = '<a href="/me/%d">%s</a>'
        elif p_type == PG_TYPE.BM_EXCEPTION:
            template_tuple = '<a href="/pe/%d">%s</a>'
        elif p_type == PG_TYPE.P2_EXCEPTION:
            template_tuple = '<a href="/pade/%d">%s</a>'

        return ''.join(template_tuple)

    last_pg = (all_count // col_per_page) + \
              (1 if (all_count % col_per_page) else 0)

    if now_pg < 1:
        now_pg = 1
    elif now_pg > last_pg:
        now_pg = last_pg

    # numbers width
    if p_type in {PG_TYPE.M_GATHER, PG_TYPE.M_CATEGORY}:
        sides = 3
    else:
        sides = 5
    begin_pg = now_pg - sides
    end_pg = now_pg + sides

    if begin_pg < 1:
        end_pg += 1 - begin_pg

    if end_pg > last_pg:
        begin_pg -= end_pg - last_pg
        end_pg = last_pg

    if begin_pg < 1:
        begin_pg = 1

    # format template
    template = template_cache.get((p_type, category))
    if template is None:
        template = make_pattern(p_type, category)
        template_cache[(p_type, category)] = template

    # mobile
    if p_type in {PG_TYPE.M_GATHER, PG_TYPE.M_CATEGORY}:

        # nag
        lst1 = list()
        # 首页
        if now_pg > 1:
            s = template % (1, '首页')
            lst1.append(s)
        else:
            lst1.append('首页')

        # 末页
        if now_pg < last_pg:
            s = template % (last_pg, '末页&nbsp;&nbsp;&nbsp;')
            lst1.append(s)
        else:
            lst1.append('末页&nbsp;&nbsp;&nbsp;')

        # 上页
        if now_pg > 1:
            s = template % (now_pg - 1, '上页')
            lst1.append(s)
        else:
            lst1.append('上页')

        # 下页
        if now_pg < last_pg:
            s = template % (now_pg + 1, '下页')
            lst1.append(s)
        else:
            lst1.append('下页')

        # numbers
        lst2 = list()
        lst2.append('共%d页' % last_pg)
        for i in range(begin_pg, end_pg + 1):
            if i == now_pg:
                ts = '<strong>%d</strong>' % i
            else:
                ts = template % (i, str(i))
            lst2.append(ts)

        return '&nbsp;&nbsp;'.join(lst2) + \
               '<br>' + \
               '&nbsp;&nbsp;'.join(lst1)

    # pc & pad
    else:
        lst = list()

        lst.append('共%d页' % last_pg)

        # 首页
        if now_pg > 1:
            s = template % (1, '首页')
            lst.append(s)
        else:
            lst.append('已到')

        # 末页
        if now_pg < last_pg:
            s = template % (last_pg, '末页')
            lst.append(s)
        else:
            lst.append('已到')

        # numbers
        for i in range(begin_pg, end_pg + 1):
            if i == now_pg:
                ts = '<strong>%d</strong>' % i
            else:
                ts = template % (i, str(i))
            lst.append(ts)

        # 上页
        if now_pg > 1:
            s = template % (now_pg - 1, '上页')
            lst.append(s)
        else:
            lst.append('已到')

        # 下页
        if now_pg < last_pg:
            s = template % (now_pg + 1, '下页')
            lst.append(s)
        else:
            lst.append('已到')

        return ' '.join(lst)  # 一个空格

#-------------------------------
#           generate_list
#-------------------------------
# generate list


def generate_list(username, category, pagenum,
                  p_type, dv_type,
                  encoded_url=''):
    if pagenum < 1:
        pagenum = 1

    # limit and offset
    # 手机版、大屏手机版、电脑版、PAD版
    if dv_type == DV_TYPE.MOBILE:
        limit = db.get_colperpagemobile()
    elif dv_type == DV_TYPE.BIGMOBILE:
        limit = db.get_colperpagebm_by_user(username)
    elif dv_type == DV_TYPE.COMPUTER:
        limit = db.get_colperpage_by_user(username)
    else:
        limit = db.get_colperpagepad_by_user(username)
    offset = limit * (pagenum - 1)

    # usertype
    usertype = db.get_usertype(username)

    # content list
    if p_type == PG_TYPE.SOURCE:
        sid = db.get_sid_by_encoded(username, encoded_url)
        all_count, lst = db.get_infos_by_sid(username, sid, offset, limit)
        if all_count is None:
            return None, None, None, None, None
    elif p_type in {PG_TYPE.P2_EXCEPTION,
                    PG_TYPE.BM_EXCEPTION,
                    PG_TYPE.M_EXCEPTION}:
        if usertype == 2:
            category = '所有用户的异常信息'
            all_count, lst = db.get_infos_all_exceptions(offset, limit)
        else:
            category = '当前用户的异常信息'
            all_count, lst = db.get_infos_user_exception(
                username, offset, limit)
    else:
        all_count, lst = db.get_infos_by_user_category(
            username, category,
            offset, limit)
        if all_count is None:
            return None, None, None, None, None

    # nag part
    page_html = generate_page(all_count, pagenum,
                              limit,
                              p_type, category)

    # current time
    int_now_time = int(time.time())

    # 时:分:秒
    now_time = datetime.datetime.\
        fromtimestamp(int_now_time).\
        strftime('%H:%M:%S')

    ago_180day = int_now_time - 3600 * 24 * 180
    ago_8h = int_now_time - 3600 * 8
    ago_24h = int_now_time - 3600 * 24

    for i in lst:
        # 180天之内
        if i.fetch_date >= ago_180day:
            # 8小时之内
            if i.fetch_date >= ago_8h:
                i.temp = 1
            # 24小时之内
            elif i.fetch_date >= ago_24h:
                i.temp = 2

            # 月-日 时:分
            i.fetch_date = datetime.datetime.\
                fromtimestamp(i.fetch_date).\
                strftime('%m-%d %H:%M')
        else:
            # 年-月-日
            i.fetch_date = datetime.datetime.\
                fromtimestamp(i.fetch_date).\
                strftime('%Y-%m-%d')

    if p_type in {PG_TYPE.GATHER, PG_TYPE.M_GATHER,
                  PG_TYPE.P2_GATHER, PG_TYPE.BM_GATHER}:
        if category == 0:
            category = '普通、关注、重要'
        elif category == 1:
            category = '关注、重要'
        elif category == 2:
            category = '重要'
    elif p_type == PG_TYPE.SOURCE:
        category = db.get_name_by_sid(sid)

    return lst, all_count, page_html, now_time, category

# return username or None


def check_cookie():
    ha = request.cookies.get('user')
    if ha:
        # return username or None
        return db.get_user_from_hash(ha)
    else:
        return None


@web.route('/')
def index():
    if not check_cookie():
        return jump_to_login

    return render_template('main.html')


@web.route('/login', methods=['GET', 'POST'])
def login():
    # check hacker
    ip = request.remote_addr
    allow, message = login_manager.login_check(ip)
    if not allow:
        return message

    # load 0 user
    if db.get_user_number() == 0:
        return render_template('login.html', msg=zero_user_loaded)

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        ha = db.login(username, password)

        if ha:
            subname = request.form.get('name')
            if subname == 'toc':
                target = '/'
            elif subname == 'top':
                target = '/pad0'
            elif subname == 'tob':
                target = '/p'
            else:
                target = '/m'
            response = make_response(redirect(target))

            # 失效期2038年
            response.set_cookie('user',
                                value=ha,
                                expires=2147483640)
            return response
        else:
            msg = login_manager.login_fail(ip)
            return render_template('login.html',
                                   msg=msg)

    return render_template('login.html')


def general_index(page_type):
    username = check_cookie()
    if not username:
        return jump_to_login

    # user type
    usertype = db.get_usertype(username)
    allow = True if usertype > 0 else False

    if request.method == 'POST':
        name = request.form.get('name')

        # logout
        if name == 'logout':
            html = jump_to_login
            response = make_response(html)
            response.set_cookie('user', expires=0)
            return response

        # fetch my sources
        elif usertype > 0 and name == 'fetch_mine':
            lst = db.get_fetch_list_by_user(username)
            c_message.make(web_back_queue, 'wb:request_fetch',
                           wvars.cfg_token, lst)

    # category list
    category_list = db.get_category_list_by_username(username)

    # 异常信息
    if usertype == 2:
        except_num = db.get_all_exception_num()
        if except_num > 0:
            except_num = '所有用户有%d条异常信息' % except_num
        else:
            except_num = None
    else:
        except_num = db.get_exceptions_num_by_username(username)
        if except_num > 0:
            except_num = '当前用户有%d条异常信息' % except_num
        else:
            except_num = None

    # render template
    if page_type == DV_TYPE.COMPUTER:
        page = 'left.html'
    elif page_type == DV_TYPE.BIGMOBILE:
        page = 'p.html'
    else:
        page = 'm.html'

    return render_template(page,
                           usertype=user_type_str[usertype],
                           username=username,
                           allowfetch=allow,
                           categories=category_list,
                           except_num=except_num)


@web.route('/left', methods=['GET', 'POST'])
def left():
    return general_index(DV_TYPE.COMPUTER)


@web.route('/ajax_exception')
def ajax_exception():
    username = check_cookie()
    if not username:
        return '尚未登录'

    if db.get_usertype(username) == 2:
        except_num = db.get_all_exception_num()
        if except_num > 0:
            ret = '所有用户有<br>%d条异常信息<br>' % except_num
        else:
            ret = ''
    else:
        except_num = db.get_exceptions_num_by_username(username)
        if except_num > 0:
            ret = '%d条异常信息<br>' % except_num
        else:
            ret = ''

    return ret


@web.route('/m', methods=['GET', 'POST'])
def mobile():
    return general_index(DV_TYPE.MOBILE)


@web.route('/p', methods=['GET', 'POST'])
def pad():
    return general_index(DV_TYPE.BIGMOBILE)

# 各页面通用的列表生成


def general_list(category, pagenum, p_type, dv_type, encoded_url=''):
    username = check_cookie()
    if not username:
        return jump_to_login

    t1 = time.perf_counter()

    lst, all_count, page_html, now_time, category = \
        generate_list(username, category,
                      pagenum, p_type, dv_type, encoded_url)

    if lst is None:
        return wrong_key_html

    if dv_type == DV_TYPE.MOBILE:
        page = 'mlist.html'
    elif dv_type == DV_TYPE.BIGMOBILE:
        page = 'plist.html'
    else:
        page = 'list.html'

    t2 = time.perf_counter()
    during = '%.5f' % (t2 - t1)

    return render_template(page,
                           entries=lst, listname=category,
                           count=all_count, htmlpage=page_html,
                           nowtime=now_time, time=during)


@web.route('/ml/<category>')
@web.route('/ml/<category>/<int:pagenum>')
def mobile_list(category, pagenum=1):
    return general_list(category, pagenum,
                        PG_TYPE.M_CATEGORY, DV_TYPE.MOBILE)


@web.route('/ml<int:level>')
@web.route('/ml<int:level>/<int:pagenum>')
def mobile_default(level, pagenum=1):
    return general_list(level, pagenum,
                        PG_TYPE.M_GATHER, DV_TYPE.MOBILE)


@web.route('/list/<category>')
@web.route('/list/<category>/<int:pagenum>')
def computer_list(category, pagenum=1):
    return general_list(category, pagenum,
                        PG_TYPE.CATEGORY, DV_TYPE.COMPUTER)


@web.route('/list<int:level>')
@web.route('/list<int:level>/<int:pagenum>')
def computer_default(level, pagenum=1):
    return general_list(level, pagenum,
                        PG_TYPE.GATHER, DV_TYPE.COMPUTER)


@web.route('/plist/<category>')
@web.route('/plist/<category>/<int:pagenum>')
def pad_list(category, pagenum=1):
    return general_list(category, pagenum,
                        PG_TYPE.BM_CATEGORY, DV_TYPE.BIGMOBILE)


@web.route('/plist<int:level>')
@web.route('/plist<int:level>/<int:pagenum>')
def pad_default(level, pagenum=1):
    return general_list(level, pagenum,
                        PG_TYPE.BM_GATHER, DV_TYPE.BIGMOBILE)


@web.route('/pe')
@web.route('/pe/<int:pagenum>')
def bm_exception(pagenum=1):
    return general_list(None, pagenum,
                        PG_TYPE.BM_EXCEPTION, DV_TYPE.BIGMOBILE)


@web.route('/me')
@web.route('/me/<int:pagenum>')
def m_exception(pagenum=1):
    return general_list(None, pagenum,
                        PG_TYPE.M_EXCEPTION, DV_TYPE.MOBILE)


@web.route('/slist<encoded_url>')
@web.route('/slist<encoded_url>/<int:pagenum>')
def slist(encoded_url='', pagenum=1):
    return general_list(encoded_url, pagenum,
                        PG_TYPE.SOURCE, DV_TYPE.COMPUTER, encoded_url)


def general_pad2(category, pagenum, p_type):
    username = check_cookie()
    if not username:
        return jump_to_login

    t1 = time.perf_counter()

    # 横竖屏，默认竖屏
    orientation = request.cookies.get('orientation')
    landscape = True if orientation == 'landscape' else False

    # user type
    usertype = db.get_usertype(username)
    allow = True if usertype > 0 else False

    if request.method == 'POST':
        name = request.form.get('name')

        # logout
        if name == 'logout':
            html = jump_to_login
            response = make_response(html)
            response.set_cookie('user', expires=0)
            return response

        # 横竖屏，默认竖屏
        elif name == 'switch':
            response = make_response(redirect('/pad0'))
            v = 'portrait' if orientation == 'landscape' else 'landscape'
            response.set_cookie('orientation',
                                value=v,
                                expires=2147483640)
            return response

        # fetch my sources
        elif usertype > 0 and name == 'fetch_mine':
            lst = db.get_fetch_list_by_user(username)
            c_message.make(web_back_queue, 'wb:request_fetch',
                           wvars.cfg_token, lst)

    # category list
    category_list = db.get_category_list_by_username(username)

    # list
    lst, all_count, page_html, now_time, category = \
        generate_list(username, category,
                      pagenum, p_type, DV_TYPE.PAD)
    if lst is None:
        return wrong_key_html

    # exceptions number
    if usertype == 2:
        exception_num = db.get_all_exception_num()
        if exception_num > 0:
            exception_num = '所有用户有%d条异常信息' % exception_num
        else:
            exception_num = None
    else:
        exception_num = db.get_exceptions_num_by_username(username)
        if exception_num > 0:
            exception_num = '当前用户有%d条异常信息' % exception_num
        else:
            exception_num = None

    t2 = time.perf_counter()
    during = '%.5f' % (t2 - t1)

    return render_template('pad.html',
                           landscape=landscape,
                           usertype=user_type_str[usertype],
                           username=username,
                           allowfetch=allow,
                           categories=category_list,
                           entries=lst, listname=category,
                           count=all_count, htmlpage=page_html,
                           nowtime=now_time, time=during,
                           exception_num=exception_num
                           )


@web.route('/pad<int:level>', methods=['GET', 'POST'])
@web.route('/pad<int:level>/<int:pagenum>', methods=['GET', 'POST'])
def pad2_default(level, pagenum=1):
    return general_pad2(level, pagenum, PG_TYPE.P2_GATHER)


@web.route('/pad/<category>', methods=['GET', 'POST'])
@web.route('/pad/<category>/<int:pagenum>', methods=['GET', 'POST'])
def pad2_list(category, pagenum=1):
    return general_pad2(category, pagenum, PG_TYPE.P2_CATEGORY)


@web.route('/pade', methods=['GET', 'POST'])
@web.route('/pade/<int:pagenum>', methods=['GET', 'POST'])
def pad_exceptions(pagenum=1):
    return general_pad2(None, pagenum, PG_TYPE.P2_EXCEPTION)


@web.route('/cateinfo', methods=['GET', 'POST'])
def cate_info():
    username = check_cookie()
    if not username:
        return jump_to_login

    usertype = db.get_usertype(username)

    if request.method == 'POST':
        if usertype > 0:
            if 'name' in request.form:
                name = request.form['name']
                sid = db.get_sid_by_encoded(username, name)
                if not sid:
                    return '请求的信息源有误：<br>' + name
                c_message.make(web_back_queue, 'wb:request_fetch',
                               wvars.cfg_token, [sid])
            elif 'cate' in request.form:
                cate = request.form['cate']
                lst = db.get_cate_list_for_fetch(username, cate)
                if lst is None:
                    return '请求的版块列表有误：<br>' + cate
                c_message.make(web_back_queue, 'wb:request_fetch',
                               wvars.cfg_token, lst)
        return ''

    show_list = db.get_forshow_by_user(username)
    all_s_num, set_s_num = db.get_sourcenum_by_user(username)

    return render_template('cateinfo.html', show_list=show_list,
                           cate_num=len(show_list),
                           allnum=all_s_num, setnum=set_s_num,
                           usertype=usertype)


def zip_cfg():
    # del .zip files in temp directory first
    files = os.listdir(wvars.upload_forlder)
    for f in files:
        fpath = os.path.join(wvars.upload_forlder, f)
        if os.path.isfile(fpath) and f.endswith('.zip'):
            try:
                os.remove(fpath)
            except:
                pass

    # target file-name
    int_now_time = int(time.time())
    date_str = datetime.datetime.\
        fromtimestamp(int_now_time).\
        strftime('%y%m%d_%H%M')
    dst = 'cfg' + date_str
    dst = os.path.join(wvars.upload_forlder, dst)

    root_path = gcfg.root_path
    newfile = shutil.make_archive(dst, 'zip', root_path, 'cfg')

    return wvars.upload_forlder, os.path.split(newfile)[1]


def prepare_db_for_download():
    # del .db files in temp directory first
    files = os.listdir(wvars.upload_forlder)
    for f in files:
        fpath = os.path.join(wvars.upload_forlder, f)
        if os.path.isfile(fpath) and f.endswith('.db'):
            try:
                os.remove(fpath)
            except:
                pass

    # current db
    db.compact_db()
    db_file, db_size = db.get_current_file()

    # target file-name
    int_now_time = int(time.time())
    date_str = datetime.datetime.\
        fromtimestamp(int_now_time).\
        strftime('%y%m%d_%H%M%S')
    dst = 'sql' + date_str + '.db'
    dst = os.path.join(wvars.upload_forlder, dst)

    # copy from database directory
    newfile = shutil.copy2(db_file, dst)

    return wvars.upload_forlder, os.path.split(newfile)[1]


@web.route('/panel', methods=['GET', 'POST'])
def panel():
    username = check_cookie()
    if not username:
        return jump_to_login

    usertype = db.get_usertype(username)

    if usertype == 2 and request.method == 'POST':
        if 'name' in request.form:
            name = request.form['name']

            # download cfg.zip
            if name == 'download_cfg':
                fpath, fname = zip_cfg()
                return send_from_directory(directory=fpath,
                                           filename=fname,
                                           as_attachment=True)
            # 压缩数据库
            elif name == 'compact_db':
                print('try to compact database file')
                db.compact_db()

            # 下载数据库
            elif name == 'download_db':
                fpath, fname = prepare_db_for_download()
                return send_from_directory(directory=fpath,
                                           filename=fname,
                                           as_attachment=True)

            # 更新所有
            elif name == 'fetch_all':
                c_message.make(web_back_queue, 'wb:request_fetch',
                               wvars.cfg_token)

            # 删除所有异常
            elif name == 'del_except':
                print('try to delete all exceptions')
                db.del_all_exceptions()

            elif name == 'backup_db':
                db.compact_db()
                db.backup_db()

            elif name == 'reload_data':
                c_message.make(web_back_queue, 'wb:request_load')

            elif name == 'maintain_db':
                db.db_process()

        elif 'fetch' in request.form:
            sid = request.form['fetch']
            if db.is_valid_sid(sid):
                c_message.make(web_back_queue,
                               'wb:request_fetch',
                               wvars.cfg_token,
                               [sid]
                               )

        elif 'file' in request.files:
            f = request.files['file']
            if f and f.filename and f.filename.lower().endswith('.zip'):
                # save to file
                fpath = os.path.join(wvars.upload_forlder, 'uploaded.zip')
                f.save(fpath)

                if not is_zipfile(fpath):
                    return '无效zip文件'

                cfg_path = os.path.join(gcfg.root_path, 'cfg')
                zftmp = os.path.join(wvars.upload_forlder, 'tmp')

                # remove & make tmp dir
                if os.path.isdir(zftmp):
                    try:
                        shutil.rmtree(zftmp)
                    except Exception as e:
                        print('删除/temp/tmp时出现异常。', e)

                try:
                    os.mkdir(zftmp)
                except Exception as e:
                    print('创建/temp/tmp时出现异常。', e)

                # extract to tmp dir
                try:
                    zf = ZipFile(fpath)
                    namelist = zf.namelist()
                    zf.extractall(zftmp)
                    zf.close()
                except Exception as e:
                    return '解压错误' + str(e)

                # copy to cfg dir
                if 'config.ini' in namelist:
                    cp_src_path = zftmp
                elif 'cfg/config.ini' in namelist:
                    cp_src_path = os.path.join(zftmp, 'cfg')
                else:
                    return 'zip文件里没有找到config.ini文件'

                try:
                    shutil.rmtree(cfg_path)
                except Exception as e:
                    return '无法删除cfg目录' + str(e)

                try:
                    shutil.copytree(cp_src_path, cfg_path)
                except Exception as e:
                    return '无法复制cfg目录' + str(e)

                print('.zip has been extracted')

                c_message.make(web_back_queue, 'wb:request_load')

    show_exceptions = db.should_show_exceptions(username)
    db_file, db_size = db.get_current_file()
    info_lst = get_info_list(gcfg, usertype, show_exceptions,
                             db_file, db_size)
    proc_lst = get_python_process(gcfg)

    # exception infos
    if usertype == 2:
        exceptions = db.get_all_exceptions()
    else:
        exceptions = db.get_exceptions_by_username(username)

    for i in exceptions:
        i.fetch_date = datetime.datetime.\
            fromtimestamp(i.fetch_date).\
            strftime('%y-%m-%d %H:%M')

    return render_template('panel.html', type=usertype,
                           info_list=info_lst, proc_list=proc_lst,
                           entries=exceptions)


@web.route('/listall')
def listall():
    username = check_cookie()
    if not username:
        return jump_to_login

    usertype = db.get_usertype(username)
    if usertype != 2:
        return '请使用管理员账号查看此页面'

    listall = db.get_listall()
    return render_template('listall.html', items=listall,
                           user_num=db.get_user_number(),
                           source_num=len(listall)
                           )


@web.route('/viewerror', methods=['GET', 'POST'])
def viewerror():
    username = check_cookie()
    if not username:
        return jump_to_login

    usertype = db.get_usertype(username)
    if usertype != 2:
        return '请使用管理员账号查看此页面'

    # path of weberr.txt
    fpath = os.path.join(wvars.upload_forlder, 'weberr.txt')

    # clear exsiting file
    if request.method == 'POST' and \
       request.form.get('name') == 'clear':
        try:
            os.remove(fpath)
        except:
            pass

    # read content
    if not os.path.isfile(fpath):
        lines = ['目前不存在此文件']
    else:
        try:
            with open(fpath) as f:
                lines = f.readlines()
        except Exception as e:
            lines = ['读取文件出现异常：\n' + str(e)]

    return render_template('viewerror.html', lines=lines)


@web.errorhandler(404)
def page_not_found(e):
    s = ('无效网址<br>'
         '<a href="/" target="_top">点击此处返回首页</a>'
         )
    return s


def write_weberr(exception):
    # del weberr.txt if size > 1M
    fpath = os.path.join(wvars.upload_forlder, 'weberr.txt')
    try:
        size = os.path.getsize(fpath)
    except:
        size = -1

    if size > 1024 * 1024:
        try:
            os.remove(fpath)
        except:
            pass

    # write to weberr.txt
    with open(fpath, 'a') as f:
        f.write(time.strftime('%Y-%m-%d %a %H:%M:%S') + '\n' +
                str(type(exception)) + '\n' +
                str(exception) + '\n\n')

    # print to console
    print('web-side exception:', str(exception))

# log in manager
login_manager = c_login_manager(write_weberr)


@web.errorhandler(500)
def internal_error(exception):
    # beep
    if winsound is not None:
        try:
            winsound.Beep(600, 1000)
        except:
            pass

    write_weberr(exception)
    return str(exception)


@web.route('/check')
def check_bw_queue():
    if request.remote_addr != '127.0.0.1':
        print('%s请求检查web端队列，忽略' % request.remote_addr)
        return ''

    print('/check')

    while True:
        try:
            msg = back_web_queue.get(block=False)
        except queue.Empty:
            break

        if msg.token == wvars.cfg_token:
            if msg.command == 'bw:success_infos':
                # [sid, fetch_time_str, info list]
                db.success_infos(msg.data[0],
                                 msg.data[1],
                                 msg.data[2])
                # feedback
                c_message.make(web_back_queue, 'wb:source_updated',
                               wvars.cfg_token,
                               msg.data[:2])  # [sid, fetch_time_str]

            elif msg.command == 'bw:exception_info':
                # msg.data is [einfo]
                db.exception_info(msg.data)

            elif msg.command == 'bw:db_process_time':
                db.db_process()
                login_manager.maintenace()

            elif msg.command == 'bw:source_timeout':
                for sid, stime, ttime in msg.data:
                    start = str(datetime.datetime.fromtimestamp(stime))
                    s = '%s超时，始于%s，超时限制%d秒' % (sid, start, ttime)
                    write_weberr(Exception(s))

        elif msg.command == 'bw:send_config_users':
                # token
            wvars.cfg_token = msg.data[0]

            # config
            cfg = msg.data[1]
            cfg.web_pid = os.getpid()
            print('pid(web, back):', cfg.web_pid, cfg.back_pid)

            global gcfg
            gcfg = cfg

            template_cache.clear()

            # users
            users = msg.data[2]
            print('web-side got users: %d' % len(users))
            db.add_users(cfg, users)

        else:
            print('web can not handle:', msg.command, msg.token)

    return ''


def run_web(web_port, certfile, keyfile, tmpfs_path,
            wb_queue, bw_queue):

    # queues
    global web_back_queue
    web_back_queue = wb_queue

    global back_web_queue
    back_web_queue = bw_queue

    # database
    global db
    db = c_db_wrapper(tmpfs_path)

    c_message.make(web_back_queue, 'wb:request_load')

    # tornado不支持Windows上的ProactorEventLoop
    # Python 3.8在Windows上默认使用ProactorEventLoop
    # 手动使用SelectorEventLoop
    if os.name == 'nt':
        import asyncio
        asyncio.DefaultEventLoopPolicy = \
            asyncio.WindowsSelectorEventLoopPolicy

    # tornado
    from tornado.wsgi import WSGIContainer
    from tornado.httpserver import HTTPServer
    from tornado.ioloop import IOLoop

    try:
        if certfile:
            import ssl
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

            cf = os.path.join(wvars.root_path, certfile)
            if keyfile:
                kf = os.path.join(wvars.root_path, keyfile)
            else:
                kf = None

            context.load_cert_chain(certfile=cf, keyfile=kf)
        else:
            context = None

        http_server = HTTPServer(WSGIContainer(web), ssl_options=context)
        http_server.listen(web_port)
        IOLoop.instance().start()
    except Exception as e:
        print('启动web服务器时出现异常，异常信息:')
        print(e)

    #-----------------
    # web service
    #-----------------
    # web.run(host='0.0.0.0', port=web_port)#, debug=True)
