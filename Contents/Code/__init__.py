# -*- coding: utf-8 -*-
import re, urllib, urllib2

main_url = 'http://www.telewizjada.net'
get_channels = 'get_channels.php'
get_channel = 'get_mainchannel.php'
get_channel_url = 'get_channel_url.php'
set_cookie = 'set_cookie.php'

PREFIX = '/video/telewizjada'
ART = 'fanart.png'
ICON = 'icon.png'
NAME = L('NAME')
HOST = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:19.0) Gecko/20121213 Firefox/19.0'

def Start():
    Plugin.AddViewGroup("Details", viewMode="InfoList")
    Plugin.AddViewGroup("List", viewMode = "List")
    ObjectContainer.art = R(ART)
    ObjectContainer.title1 = NAME
    ObjectContainer.view_group = "List"
    DirectoryObject.thumb = R(ICON)
    HTTP.User_Agent = HOST


@handler(PREFIX, NAME, ICON, ART)
def MainMenu():
    oc = ObjectContainer()
    oc.no_cache = True
    data = GetDataFromApi()

    oc.add(DirectoryObject(key=Callback(GetChannels,category='all'),title=L('MENU_ALL_CHANNELS')))
    oc.add(DirectoryObject(key=Callback(GetChannels,category='online'),title=L('MENU_ONLINE_CHANNELS')))
    for category in data['categories']:
        # Log(category)
        if not (category['Categoryid'] == 8 and Prefs['hideAdultContent']):
            oc.add(DirectoryObject(key=Callback(GetChannels,category=category['Categoryid']),title=category['Categoryname']))
    oc.add(PrefsObject(title=L("STRING_SETTINGS")))
    return oc
    

@route(PREFIX + '/{category}')
def GetChannels(category):
    oc = ObjectContainer()
    oc.view_group = "Details"

    channels = []
    data = GetDataFromApi()
    if category == 'all':
        Log('Getting all channels')
        channels = data['channels']
        oc.title2 = L('MENU_ALL_CHANNELS')
    elif category == 'online':
        Log('Getting online channels')
        for channel in data['channels']:
            if channel['online']:
                channels.append(channel)
        oc.title2 = L('MENU_ONLINE_CHANNELS')
    else:
        for cat in data['categories']:
            if cat['Categoryid'] == int(category):
                Log('Getting channels for category \'{}\''.format(cat['Categoryname']))
                channels = cat['Categorychannels']
                oc.title2 = cat['Categoryname']
                break

    if channels:
        for channel in channels:
            if not (Prefs['hideAdultContent'] and channel['isAdult']):
                oc.add(
                    VideoClipObject(
                        key=Callback(GetChannel,cid=channel['id']),
                        title=channel['displayName'] if channel['online'] else "[OFFLINE] " + channel['displayName'],
                        summary = 'ONLINE' if channel['online'] else 'OFFLINE',
                        rating_key=channel['displayName'],
                        thumb=main_url + channel['thumb']
                    )
                )
        return oc
    else:
        return MessageContainer('ERROR',L("ERROR_NO_CHANNELS"))


@route(PREFIX + '/channel/{cid}')
def GetChannel(cid, container = True):

    channel = GetChannelFromApi(cid)

    if channel['online']:
        media = VideoClipObject(
            key = Callback(GetChannel, cid=cid, container=True),
            rating_key = channel['name'],
            title = channel['displayName'],
            thumb = main_url + channel['bigThumb'],
            items = [
                MediaObject(
                    # container = Container.MP4,     # MP4, MKV, MOV, AVI
                    # video_codec = VideoCodec.H264, # H264
                    # audio_codec = AudioCodec.AAC,  # ACC, MP3
                    video_resolution = 576,
                    optimized_for_streaming = True,
                    parts = GetStreams(channel)
                )
            ]
        )

        if container:
            return ObjectContainer(objects=[media],no_cache=True)
        else:
            return media
    else:
        return MessageContainer('ERROR',str(L("ERROR_CHANNEL_OFFLINE")).format(channel['displayName']))


def GetDataFromApi():
    url = '{}/{}'.format(main_url,get_channels)
    try:
        data = JSON.ObjectFromURL(url=url,cacheTime=30)
    except Exception, err:
        Log('Failed to retrieve list of channels and categories from url={}'.format(url))
        Log('API error: {}'.format(err))
    else:
        return data


def GetChannelFromApi(cid):
    url = '{}/{}'.format(main_url,get_channel)
    params = {'cid': cid}
    try:
        data = JSON.ObjectFromURL(url=url,values=params,cacheTime=0)
    except Exception, err:
        Log('Failed to get channel data from url={}, post={}'.format(url,params))
        Log('API error: {}'.format(err))
    else:
        return data


def GetVideoURLFromApi(cid, cookies):
    url = '{}/{}'.format(main_url,get_channel_url)
    params = {'cid': cid}
    headers = {'Cookie':cookies,'User-Agent':HOST}
    try:
        data = JSON.ObjectFromURL(url=url,values=params,headers=headers,cacheTime=0)
    except Exception, err:
        Log('Failed to get video URL from url={}, post={}, headers={}'.format(url,params,headers))
        Log('API error: {}'.format(err))
    else:
        return data


def GetStreams(channel):
    parts = []
    cookies = GetCookies(channel['url'])
    url_data = GetVideoURLFromApi(channel['id'], cookies)
    streams = CreateStreamList(url_data['url'], cookies)
    Log('URL data = {}, Cookie = {}, Streams = {}'.format(url_data,cookies,streams))
    for stream in streams:
        parts.append(PartObject(key = HTTPLiveStreamURL(url=stream)))
    return parts


def CreateStreamList(url, cookies):
        root_url = url.rsplit('playlist',1)[0]
        headers = {'Cookie':cookies,'User-Agent':HOST}
        playlist = HTTP.Request(url, headers=headers, cacheTime=0).content
        streams = []
        for line in playlist.splitlines():
            if not line.startswith('#'):
                streams.append(root_url + line)
        return streams


def GetCookies(channel_url):
    url = '{}/{}'.format(main_url,set_cookie)
    params = {'url': channel_url}
    try:
        handler = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        post_data = urllib.urlencode(params)
        request = urllib2.Request(url, post_data)
        request.add_header('User-Agent',HOST)
        response = handler.open(request)
        response.close()
        return (response.info()['Set-Cookie'])
        # VVV This does not work VVV
        # data = HTTP.Request(url, values=params, headers={'User-Agent':HOST})
        # Log(data.content)
        # Log(data.headers)
        # cookie = data.headers['set-cookie']
        # Log(cookie)
        # return cookie
    except Exception, err:
        Log('Failed to get cookies from url={}, post={}'.format(url,params))
        Log('API error: {}'.format(err))


def ChannelOffline(channel_name):
    return ObjectContainer(header="Empty",message=str(L("ERROR_CHANNEL_OFFLINE")).format(channel_name))
