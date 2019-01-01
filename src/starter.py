#! /usr/bin/python3
# coding=utf-8

version = 'InfoPi v.2019-1-1'


def main():
    # -------------------
    #      import
    # -------------------
    import os
    import shutil
    import argparse
    import multiprocessing

    import wvars

    def get_src_subdir(sub):
        ret = os.path.dirname(os.path.realpath(__file__))
        ret = os.path.join(ret, sub)
        return ret

    def get_root_subdir(sub):
        ret = os.path.join(wvars.root_path, sub)
        return ret

    # argparse
    parser = argparse.ArgumentParser()

    # tmpfs
    parser.add_argument('-t', '--tmpfs',
                        type=str, help='内存临时文件夹',
                        metavar='路径',
                        default='',
                        dest='tmpfs_path')

    # port
    parser.add_argument('-p', '--port',
                        type=int, help='使用的端口',
                        metavar='端口',
                        default=5000,
                        dest='web_port')

    # certfile keyfile
    parser.add_argument('-c', '--certfile',
                        type=str, help='证书文件，应位于程序根目录下',
                        metavar='文件名',
                        default='',
                        dest='certfile')

    parser.add_argument('-k', '--keyfile',
                        type=str, help='密钥文件，应位于程序根目录下',
                        metavar='文件名',
                        default='',
                        dest='keyfile')

    args = parser.parse_args()

    tmpfs_path = args.tmpfs_path
    web_port = args.web_port

    certfile = args.certfile
    keyfile = args.keyfile

    # ------------------------

    if tmpfs_path:
        try:
            shutil.rmtree(tmpfs_path)
        except:
            pass

        try:
            os.mkdir(tmpfs_path)
        except:
            pass

        # static/template dir
        wvars.static_folder = os.path.join(tmpfs_path, 'static')
        wvars.template_folder = os.path.join(tmpfs_path, 'templates')
        # copy folders
        shutil.copytree(get_src_subdir('static'), wvars.static_folder)
        shutil.copytree(get_src_subdir('templates'), wvars.template_folder)

        # temp dir
        wvars.upload_forlder = os.path.join(tmpfs_path, 'temp')
        try:
            os.mkdir(wvars.upload_forlder)
        except:
            pass

    else:
        wvars.upload_forlder = get_root_subdir('temp')

        # clear temp
        try:
            shutil.rmtree(wvars.upload_forlder)
        except:
            pass

        try:
            os.mkdir(wvars.upload_forlder)
        except:
            pass

    #-----------------
    # back process
    #-----------------
    from backprocess import main_process

    web_back_queue = multiprocessing.Queue()
    back_web_queue = multiprocessing.Queue()

    # back-side process
    global version
    process = multiprocessing.Process(target=main_process,
                                      args=(version,
                                            web_port, bool(certfile),
                                            tmpfs_path,
                                            web_back_queue,
                                            back_web_queue),
                                      daemon=True
                                      )
    process.start()

    #-----------------
    # web process
    #-----------------
    from webprocess import run_web
    run_web(web_port, certfile, keyfile, tmpfs_path,
            web_back_queue, back_web_queue)


if __name__ == '__main__':
    main()
