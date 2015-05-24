# coding=utf-8

import bisect
import collections
import time
import datetime
import hashlib
import base64

try:
    import winsound
except:
    has_winsound = False
else:
    has_winsound = True

from sqldb import *


class c_index_unit:
    __slots__ = ('iid', 'fetch_date')

    def __init__(self, iid, fetch_date):
        self.iid = iid
        self.fetch_date = fetch_date

    def __lt__(self, other):
        if self.fetch_date > other.fetch_date:
            return True
        elif self.fetch_date == other.fetch_date and \
             self.iid > other.iid:
            return True
        else:
            return False

    def __eq__(self, other):
        if self.iid == other.iid and \
           self.fetch_date == other.fetch_date:
            return True
        return False

    def __ne__(self, other):
        if self.iid != other.iid or \
           self.fetch_date != other.fetch_date:
            return True
        return False

    def __str__(self):
        return str(self.iid) + ',' + str(self.fetch_date)

class c_user_table:
    __slots__ = ('username', 'password', 'up_hash', 
                 'col_per_page', 'usertype',
                 'sid_level_dict', 'sid_list',
                 'cate_list', 'cate_indexlist_dict',
                 'show_list', 'appeared_source_num')

    def __init__(self):
        self.username = ''
        self.password = ''
        self.up_hash = ''
        self.col_per_page = 20
        self.usertype = 1

        # source_id -> level
        self.sid_level_dict = dict()

        # for fetch request
        self.sid_list = list()

        # 元素为tuple: (category, <list>)
        # <list>元素为source_id
        self.cate_list = list()

        # category -> <list>
        # <list>元素为c_index_unit
        self.cate_indexlist_dict = dict()

        # 元素为tuple: (category, <list>)
        # <list>元素为c_for_show
        self.show_list = list()

        # 出现的信息源数目(包括重复的)
        self.appeared_source_num = 0


class c_source_table:
    __slots__ = ('source_id', 
                 'name', 'comment', 'link', 'interval',
                 'user_cateset_dict', 'index_list')

    def __init__(self):
        self.source_id = ''

        self.name = ''
        self.comment = ''
        self.link = ''
        self.interval = 0

        # username -> <set>
        # <set>的元素为 category
        self.user_cateset_dict = dict()

        # 元素为c_index_unit
        self.index_list = list()

class c_for_show:
    __slots__ = ('name', 'comment', 'link',
                 'level_str', 'interval_str', 'encoded_url')
    
    def __init__(self):
        self.name = ''
        self.comment = ''
        self.link = ''

        self.level_str = ''
        self.interval_str = ''
        self.encoded_url = ''
        
class c_for_listall:
    __slots__ = ('source_id', 'interval_str', 'userlist',
                 'name', 'comment', 'link',
                 'color')
    
    def __init__(self):
        self.source_id = ''
        self.interval_str = ''
        self.userlist = list()
        
        self.name = ''
        self.comment = ''
        self.link = ''
        
        self.color = 0
        
    def __lt__(self, other):
        if self.source_id < other.source_id:
            return True
        else:
            return False
        
def get_interval_str(interval):
    interval_str = ''
    
    if interval >= 24*3600:
        interval_str += '%d天' % (interval//(24*3600))
        interval = interval % (24*3600)

    if interval >= 3600:
        interval_str += '%d小时' % (interval//3600)
        interval = interval % 3600

    if interval >= 60:
        interval_str += '%d分钟' % (interval//60)
        interval = interval % 60
    
    return interval_str

class c_db_wrapper:
    __slots__ = ('sqldb', 
                 'users', 'sources', 'hash_user', 
                 'ghost_sources', 'exceptions_index', 
                 'cfg', 'listall')

    def __init__(self, tmpfs_path):
        self.sqldb = c_sqldb(tmpfs_path)
        self.sqldb.set_callbacks(self.callback_append_one_info,
                                 self.callback_remove_from_indexs,
                                 self.callback_add_to_indexs)

        self.users = dict()
        self.sources = dict()

        self.hash_user = dict()

        # sid
        self.ghost_sources = set()
        
        # 元素为c_index_unit
        self.exceptions_index = list()

        self.cfg = None
        self.listall = None

    def add_infos(self, lst):
        # add one by one
        res = [self.sqldb.add_info(i) \
               for i in lst[::-1] \
               if i.source_id in self.sources]

        beep = sum(1 for i in res 
                    if i in (DB_RESULT.ADDED, DB_RESULT.UPDATED)
                    )

        if beep:
            print(time.ctime(), 'database was added or updated')
            # 发出响声
            if has_winsound:
                try:
                    winsound.Beep(350, 300)
                except:
                    pass

    def add_one_user(self, cfg, user):
        # create user_table
        ut = c_user_table()
        self.users[user.username] = ut

        ut.username = user.username
        ut.password = user.password
        ut.usertype = user.usertype
        ut.col_per_page = user.col_per_page

        # cate_indexlist_dict, for level 0, 1, 2
        ut.cate_indexlist_dict[0] = list()
        ut.cate_indexlist_dict[1] = list()
        ut.cate_indexlist_dict[2] = list()

        for cate_tuple in user.category_list:
            now_cate = cate_tuple[0]

            # cate_indexlist_dict
            ut.cate_indexlist_dict[now_cate] = list()

            # cate_list.cate
            ut.cate_list.append( (cate_tuple[0], list()) )

            for source_tuple in cate_tuple[1]:
                now_sid = source_tuple[0]

                # cate_list.cate.sid
                ut.cate_list[-1][1].append(now_sid)

                # sid_level_dict, level
                if now_sid not in ut.sid_level_dict:
                    ut.sid_level_dict[now_sid] = source_tuple[1]
                else:
                    ut.sid_level_dict[now_sid] = \
                    max(ut.sid_level_dict[now_sid], source_tuple[1])

                # sources table
                st = self.sources.setdefault(now_sid, c_source_table())
                if not st.source_id:
                    st.source_id = now_sid
                    st.interval = source_tuple[2]
                    st.name = source_tuple[3]
                    st.comment = source_tuple[4]
                    st.link = source_tuple[5]
                    #print(st.name, st.comment)

                # source_table.user_cateset_dict
                ucs = st.user_cateset_dict.setdefault(user.username, set())
                ucs.add(now_cate)

        # for category 0, 1, 2
        for category, sid_list in ut.cate_list:
            for sid in sid_list:
                level = ut.sid_level_dict[sid]

                st = self.sources[sid]
                ucs = st.user_cateset_dict[user.username]

                if level == 0:
                    ucs.add(0)
                elif level == 1:
                    ucs.add(0)
                    ucs.add(1)
                elif level == 2:
                    ucs.add(0)
                    ucs.add(1)
                    ucs.add(2)
                else:
                    print('add user: level error')

        # hash->user dict
        s = user.username + ' (^.^) ' + user.password
        up_hash = hashlib.md5(s.encode('utf-8')).hexdigest()

        self.hash_user[up_hash] = user.username
        ut.up_hash = up_hash

        # for fetch request
        ut.sid_list = list(ut.sid_level_dict.keys())

        # for show
        for cate, sid_lst in ut.cate_list:
            temp_lst = list()

            for sid in sid_lst:
                one = c_for_show()
                source = self.sources[sid]

                one.name = source.name
                one.comment = source.comment
                one.link = source.link
                #print(one.name, one.comment, one.link)

                # encoded url
                b64 = base64.urlsafe_b64encode(sid.encode('utf-8'))
                one.encoded_url = b64.decode('ascii')

                # level
                temp_level = ut.sid_level_dict[sid]
                if temp_level == 0:
                    one.level_str = '普通'
                elif temp_level == 1:
                    one.level_str = '关注'
                elif temp_level == 2:
                    one.level_str = '重要'

                # interval str
                one.interval_str = get_interval_str(source.interval)

                temp_lst.append(one)

                # count appeared source number
                ut.appeared_source_num += 1

            ut.show_list.append( (cate, temp_lst) )

        #print('显示列表 %d' % len(ut.show_list))


    def add_users(self, cfg, users_lst):
        # clear first
        self.users.clear()
        self.sources.clear()
        self.hash_user.clear()
        self.ghost_sources.clear()
        self.exceptions_index.clear()

        self.cfg = cfg

        # creat data-structs
        for user in users_lst:
            self.add_one_user(cfg, user)

        # load data to build indexs
        self.sqldb.get_all_for_make_index()

        # build listall infomation ---------------
        tempd = dict()
        for source in self.sources.values():
            item = c_for_listall()
            item.source_id = source.source_id
            item.interval_str = get_interval_str(source.interval)
            
            item.name = source.name
            item.comment = source.comment
            item.link = source.link
            
            tempd[item.source_id] = item
            
        for user, ut in self.users.items():
            for sid in ut.sid_list:
                tempd[sid].userlist.append(user)
                
        # sort by source_id
        self.listall = [item for item in tempd.values()]
        self.listall.sort()
        
        last_category = ''
        now_color = 2
        for item in self.listall:
            # sort userlist
            item.userlist.sort()
            item.userlist = '&nbsp;'.join(item.userlist)
                
            # color
            category, temp = item.source_id.split(':')
            if category != last_category:
                now_color = 2 if now_color == 1 else 1
                last_category = category
            item.color = now_color

    # --------------- callbacks -------------------

    # used for creating indexs
    def callback_append_one_info(self, source_id, iid, fetch_date, suid):
        if source_id not in self.sources:
            # print and add to ghost
            if source_id not in self.ghost_sources:
                s = 'datebase wrapper: %s is ghost source'
                print(s % source_id)         
                self.ghost_sources.add(source_id)
            return

        unit = c_index_unit(iid, fetch_date)

        # category indexs
        ucd = self.sources[source_id].user_cateset_dict
        for user, cateset in ucd.items():
            for cate in cateset:
                self.users[user].cate_indexlist_dict[cate].append(unit)

        # source index
        sindex = self.sources[source_id].index_list
        sindex.append(unit)
        
        # exception index
        if suid == '<exception>':
            self.exceptions_index.append(unit)

    # remove from indexs
    def callback_remove_from_indexs(self, source_id, iid, fetch_date, suid):
        unit = c_index_unit(iid, fetch_date)

        # category indexs
        ucd = self.sources[source_id].user_cateset_dict
        for user, cate_set in ucd.items():
            for cate in cate_set:
                index = self.users[user].cate_indexlist_dict[cate]

                p = bisect.bisect_left(index, unit)
                del index[p]

        # source index
        sindex = self.sources[source_id].index_list
        p = bisect.bisect_left(sindex, unit)
        del sindex[p]
        
        # exception index
        if suid == '<exception>':
            sindex = self.exceptions_index
            p = bisect.bisect_left(sindex, unit)
            del sindex[p]

    # add to indexs
    def callback_add_to_indexs(self, source_id, iid, fetch_date, suid):        
        unit = c_index_unit(iid, fetch_date)

        # category indexs
        ucd = self.sources[source_id].user_cateset_dict
        for user, cate_set in ucd.items():
            for cate in cate_set:
                index = self.users[user].cate_indexlist_dict[cate]
                bisect.insort_left(index, unit)

        # source index
        sindex = self.sources[source_id].index_list
        bisect.insort_left(sindex, unit)
        
        # exception index
        if suid == '<exception>':
            bisect.insort_left(self.exceptions_index, unit)

    # ----------- utility --------------
    def compact_db(self):
        self.sqldb.compact_db()

    def backup_db(self):
        self.sqldb.backup_db(self.cfg.db_backup_maxfiles)

    def db_process(self):
        print('database maintenance')

        # del too-many data
        before_del = int(time.time())-self.cfg.db_process_del_days*24*3600
        tmp_unit = c_index_unit(0, before_del)

        del_lst = list()
        for s in self.sources.values():
            sid = s.source_id
            index = s.index_list
            if len(index) > self.cfg.db_process_del_entries:
                p = bisect.bisect_left(index, tmp_unit)
                #(source_id, id, fetch_date)
                tuple_lst = ((sid, i.iid, i.fetch_date) for i in index[p:])
                del_lst.extend(tuple_lst)

        print('%d条数据将被删除' % len(del_lst))
        self.sqldb.del_info_by_tuplelist(del_lst)

        # ghost source
        if self.cfg.db_process_rm_ghost:
            for sid in self.ghost_sources:
                self.sqldb.del_ghost_by_sid(sid)
            self.ghost_sources.clear()

        # backup
        self.sqldb.compact_db()
        self.sqldb.backup_db(self.cfg.db_backup_maxfiles)

    def get_current_file(self):
        return self.sqldb.get_current_file()

    def del_exceptions_by_sid(self, lst):
        for sid in lst:
            if sid in self.sources:
                self.sqldb.del_exceptions_by_sid(sid)

    def del_all_exceptions(self):
        self.sqldb.del_all_exceptions(self.sources)

    # for left category
    def get_category_list_by_username(self, username):
        if username not in self.users:
            return None

        ut = self.users[username]
        return (cate for cate, lst in ut.cate_list)

    # return col_per_page
    def get_colperpage_by_user(self, username):
        ret = self.users[username].col_per_page
        return ret

    # len of a username.category
    def get_count_by_user_cate(self, username, category):
        try:
            lst = self.users[username].cate_indexlist_dict[category]
        except:
            return -1
        
        return len(lst)

    # for show
    def get_name_by_sid(self, sid):
        return self.sources[sid].name

    # for show
    def get_forshow_by_user(self, username):
        return self.users[username].show_list
    
    # listall
    def get_listall(self):
        return self.listall

    # for cateinfo. all/unduplicated sources number
    def get_sourcenum_by_user(self, username):
        return self.users[username].appeared_source_num, \
               len(self.users[username].sid_list)

    # len of source.index_list
    def get_count_by_sid(self, sid):
        try:
            lst = self.sources[sid].index_list
        except:
            return -1
        
        return len(lst)

    # get fetch list (sid)
    def get_fetch_list_by_user(self, username):
        ret = self.users[username].sid_list
        return ret

    def get_usertype(self, username):
        return self.users[username].usertype

    # get infos of a page
    def get_infos_by_user_category(self, 
                                   username, category, 
                                   offset, limit):
        index = self.users[username].cate_indexlist_dict[category]
        end = min(offset+limit, len(index))

        ret_list = list()
        for i in range(offset, end):
            index_unit = index[i]
            info = self.sqldb.get_info_by_iid(index_unit.iid)
            
            ret_list.append(info)

        return ret_list

    # get infos of a source
    def get_infos_by_sid(self, username, sid, offset, limit):
        if sid not in self.users[username].sid_level_dict:
            return None
        
        index = self.sources[sid].index_list
        end = min(offset+limit, len(index))

        ret_list = list()
        for i in range(offset, end):
            index_unit = index[i]
            info = self.sqldb.get_info_by_iid(index_unit.iid)
            
            ret_list.append(info)

        return ret_list

    # get all exceptions
    def get_all_exceptions(self):
        lst = list()
        for unit in self.exceptions_index:
            info = self.sqldb.get_info_by_iid(unit.iid)
            lst.append(info)

        return lst
    
    # get exceptions by username
    def get_exceptions_by_username(self, username):
        lst = list()
        for unit in self.exceptions_index:
            info = self.sqldb.get_info_by_iid(unit.iid)
            lst.append(info)
        
        d = self.users[username].sid_level_dict
        lst = [one for one in lst if one.source_id in d]
        return lst

    # ----------- for login --------------

    # login
    def login(self, username, password):
        if username not in self.users:
            return ''

        ut = self.users[username]
        if password == ut.password:
            return ut.up_hash
        else:
            return ''

    # get user from hash_user dict
    def get_user_from_hash(self, ha):
        return self.hash_user.get(ha)

    # get user number:
    def get_user_number(self):
        return len(self.users)


class c_login_manager:
    # if one ip has tried RECENT_COUNT in the
    # last RECENT_TIME, then forbid login for FORBID_TIME
    # (unit of times are seconds)
    RECENT_TIME = 3*60
    RECENT_COUNT = 4
    FORBID_TIME = 10*60

    def __init__(self):
        # ip -> <list>
        # <list>: [next_time, deque(time)]
        self.ip_dict = dict()

    def login_check(self, ip):
        now_time = int(time.time())

        if ip not in self.ip_dict:
            return True, ''
        elif now_time < self.ip_dict[ip][0]:
            delta = self.ip_dict[ip][0] - now_time
            return False, '尝试登录次数太多，请于%d秒后再试' % delta
        else:
            return True, ''

    def login_fall(self, ip):
        now_time = int(time.time())

        # del old
        self.maintenace(now_time)

        # append now_time
        if ip not in self.ip_dict:
            self.ip_dict[ip] = [0, collections.deque()]
        self.ip_dict[ip][1].append(now_time)

        # forbid
        if len(self.ip_dict[ip][1]) >= c_login_manager.RECENT_COUNT:
            self.ip_dict[ip][0] = now_time + c_login_manager.FORBID_TIME

    def maintenace(self, now_time=None):
        if now_time == None:
            now_time = int(time.time())
        recent = now_time - c_login_manager.RECENT_TIME

        temp_set = set()

        for ip, (next_time, deck) in self.ip_dict.items():
            while deck and deck[0] < recent:
                deck.popleft()

            if not deck:
                temp_set.add(ip)

        for ip in temp_set:
            del self.ip_dict[ip]

    def clear(self):
        self.ip_dict.clear()