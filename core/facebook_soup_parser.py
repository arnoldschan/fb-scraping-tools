from core import common
from core import model

from bs4 import BeautifulSoup, NavigableString
from collections import namedtuple
from collections import OrderedDict
from datetime import datetime
import json
import logging
import re


GenericResult = namedtuple('GenericResult', ['content', 'see_more_links'])
TimelineResult = namedtuple('TimelineResult', ['articles', 'show_more_link'])
ReactionResult = namedtuple('ReactionResult', ['likers', 'see_more_link'])


def detect_error_type(content):
    """
    >>> detect_error_type('<input name="login">Login requested')
    'Cookie expired or is invalid, login requested'
    >>> detect_error_type('<div id="objects_container"><span class="bb">' + \
        'The page you requested cannot be displayed at the moment. ' + \
        'It may be temporarily unavailable, the link you clicked on may ' + \
        'be broken or expired, or you may not have permission to view ' + \
        'this page.</span></div>')
    'Page temporarily unavailable / broken / expired link'
    >>> detect_error_type('<html></html>')
    'Failed to parse page'
    """
    soup = BeautifulSoup(content, "lxml")

    if soup.find("input", attrs={"name": "login"}):
        return "Cookie expired or is invalid, login requested"
    elif soup.find_all(
            "span", string=re.compile("It may be temporarily unavailable")):
        return "Page temporarily unavailable / broken / expired link"
    else:
        return "Failed to parse page"


class FacebookSoupParser:

    def parse_buddy_list(self, raw_json):
        """
        >>> FacebookSoupParser().parse_buddy_list(
        ... 'for (;;); {"ms": [{"type": "chatproxy-presence", '
        ... '"userIsIdle": false, "chatNotif": 0, "gamers": [], "buddyList": {'
        ... '"111": {"lat": 1500000001}, '
        ... '"222": {"lat": 1500000002}, '
        ... '"333": {"lat": -1}}}, {"type": "buddylist_overlay",'
        ...  '"overlay": {"333": {"la": 1500000003, "a": 0, "vc": 0, "s":'
        ... '"push"}}}], "t": "msg", "u": 123, "seq": 3}')
        OrderedDict([('111', {'times': ['2017-07-14 04:40:01']}), \
('222', {'times': ['2017-07-14 04:40:02']}), ('333', {'times': []})])
        >>> FacebookSoupParser().parse_buddy_list("")
        OrderedDict()
        >>> FacebookSoupParser().parse_buddy_list(
        ... '{ "overlay": { "111": { '
        ... '"a": 0, "c": 74, "la": 1500000003, "s": "push", "vc": 74 }}, '
        ... '"type": "buddylist_overlay"}')
        OrderedDict()
        >>> FacebookSoupParser().parse_buddy_list(
        ... '{ "seq": 1, "t": "fullReload" }')
        OrderedDict()
        """
        valid_raw_json = raw_json.replace("for (;;); ", "")
        decoded_json = ""
        try:
            decoded_json = json.loads(valid_raw_json)
        except Exception as e:
            logging.error(
                "Failed to decode JSON: '{0}', got exception:"
                " '{1}'".format(valid_raw_json, e))
            return OrderedDict()

        logging.debug("Got json: '{0}'".format(common.prettify(decoded_json)))
        if "ms" not in decoded_json:
            logging.error("Invalid json returned - not found 'ms'")
            logging.debug("Got instead: {0}".format(
                common.prettify(decoded_json)))
            return OrderedDict()

        flattened_json = {}
        for item in decoded_json["ms"]:
            flattened_json.update(item)
        if "buddyList" not in flattened_json:
            logging.error("Invalid json returned - not found 'buddyList'")
            logging.debug("Got instead: {0}".format(
                common.prettify(flattened_json)))
            return OrderedDict()

        buddy_list = flattened_json["buddyList"]
        flattened_buddy_list = {}
        for user in buddy_list:
            if "lat" in buddy_list[user]:
                times = []
                lat_found = buddy_list[user]["lat"]
                if lat_found > -1:
                    times.append(str(datetime.fromtimestamp(int(lat_found))))
                flattened_buddy_list[user] = \
                    {"times": times}

        return OrderedDict(sorted(flattened_buddy_list.items()))

    def parse_about_page(self, content):
        """Extract information from the mobile version of the about page.

        Returns an OrderedDict([('name', ''), ...]).

        Keys are added only if the fields were found in the about page.

        >>> FacebookSoupParser().parse_about_page('''
        ...    <title id="pageTitle">Mark Zuckerberg</title>
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ... ''')["name"]
        'Mark Zuckerberg'
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div class="dc dd dq" title="Birthday">
        ...             <div class="dv">14 May 1984</div>
        ...         </div>
        ...    </div>
        ...    ''')["birthday"]
        '14 May 1984'
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div class="dc dd dq" title="Birthday">
        ...             <div class="dv">14 May 1984</div>
        ...         </div>
        ...    </div>
        ...    ''')["year_of_birth"]
        1984
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div class="dc dd dq" title="Birthday">
        ...             <div class="dv">14 May</div>
        ...         </div>
        ...    </div>
        ...    ''')["day_and_month_of_birth"]
        '14 May'
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div class="_5cds _2lcw _5cdu" title="Gender">
        ...             <div class="_5cdv r">Male</div>
        ...         </div>
        ...    </div>
        ...    ''')["gender"]
        'Male'
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div class="_5cds _2lcw _5cdu" title="Gender">
        ...             <span class="du dm x">Gender</span>
        ...             <span aria-hidden="true"> · </span>
        ...             <span class="dl">Edit</span>
        ...             <div class="_5cdv r">Male</div>
        ...         </div>
        ...    </div>
        ...    ''')["gender"]
        'Male'
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div id="relationship"><div class="cq">''' + \
                    'Relationship</div><div class="cu do cv">' + \
                    'Married to <a class="bu" href="/someone">Someone</a>' + \
                    ' since 14 March 2010</div></div>' + '''
        ...    </div>
        ...    ''')["relationship"]
        'Married'
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div id="work">
        ...             <a class="bm" href="">
        ...                 <img src="" alt="1st work">
        ...             </a>
        ...             <a class="bm" href="">
        ...                 <img src="" alt="2nd work">
        ...             </a>
        ...         </div>
        ...    </div>''')["work"]
        '1st work'
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div id="education">
        ...             <a class="bm" href="">
        ...                 <img src="" alt="1st education">
        ...             </a>
        ...             <a class="bm" href="">
        ...                 <img src="" alt="2nd education">
        ...             </a>
        ...         </div>
        ...    </div>''')["education"]
        '1st education'
        >>> FacebookSoupParser().parse_about_page('''
        ...     <a href="/mark?v=timeline&amp;lst=1%3A12345%3A2">
        ...         Timeline
        ...     </a>''')["id"]
        12345
        >>> FacebookSoupParser().parse_about_page('''
        ...     <input name="login" type="submit" value="Log In">''')
        """
        soup = BeautifulSoup(content, "lxml")

        user_info = OrderedDict()

        name_tag = soup.find("title")
        if name_tag:
            user_info["name"] = name_tag.text

        timeline_tag = soup.find(href=re.compile(
            r"^/.*\?v=timeline.lst=\d+%3A\d+%3A"))
        if not timeline_tag:

            logging.error(detect_error_type(content))
            return None

        user_id = int(timeline_tag.attrs["href"].split(
            "%3A")[1])
        user_info["id"] = user_id

        tags = [
            'AIM', 'Address', 'BBM', 'Birth Name', 'Birthday',
            'Facebook', 'Foursquare', 'Gadu-Gadu', 'Gender', 'ICQ',
            'Instagram', 'Interested in', 'Languages', 'LinkedIn',
            'Maiden Name', 'Mobile', 'Nickname', 'Political Views',
            'Religious views', 'Skype', 'Snapchat', 'Twitter', 'VK',
            'Websites', 'Windows Live Messenger', 'Year of birth']

        for tag in tags:
            found_tag = soup.find("div", attrs={"title": tag})
            if found_tag:
                user_info[tag.replace(" ", "_").lower()] = found_tag.text. \
                    replace(tag, "").replace("\n", "").replace(" · Edit", "")

        if "birthday" in user_info:
            parsed_birthday = user_info["birthday"]
            if parsed_birthday.count(" ") != 2:
                user_info["day_and_month_of_birth"] = parsed_birthday
                del user_info["birthday"]
            else:
                user_info["day_and_month_of_birth"] = " ".join(
                    parsed_birthday.split(" ")[0:2])
                user_info["year_of_birth"] = parsed_birthday.split(" ")[-1]

        if "year_of_birth" in user_info:
            user_info["year_of_birth"] = int(user_info["year_of_birth"])

        institution_tags = ["work", "education"]
        for institution_tag in institution_tags:
            found_tag = soup.find("div", attrs={"id": institution_tag})
            if found_tag:
                found_img_tag = found_tag.find("img")
                if found_img_tag and "alt" in found_img_tag.attrs:
                    user_info[institution_tag] = \
                        found_img_tag.attrs["alt"]

        relationship_tag = soup.find("div", attrs={"id": "relationship"})
        if relationship_tag:

            relationship_choices = [
                'In a relationship', 'Engaged', 'Married',
                'In a civil partnership', 'In a domestic partnership',
                'In an open relationship', 'It\'s complicated', 'Separated',
                'Divorced', 'Widowed', 'Single'
            ]
            for relationship_choice in relationship_choices:
                if relationship_choice in relationship_tag.text:
                    user_info["relationship"] = relationship_choice
                    break

        return user_info

    def parse_friends_page(self, content):
        """Extract information from the mobile version of the friends page.

        JavaScript has to be disabled when fetching the page, otherwise, the
        content returned by requests does not contain the UIDs.

        Returns a GenericResult(
            content=OrderedDict([('friends',
                OrderedDict([('/link1', 'Friend 1'), ...]),
                see_more_links=[])

        >>> FacebookSoupParser().parse_friends_page('''
        ...     <div id="objects_container">
        ...         <a href="/privacyx/selector/?refid=17">
        ...         <a href="/user?v=timeline&amp;lst=link">Timeline</a>
        ...         <a href="/username1?fref=fr_tab&amp;foo">Mark</a>
        ...         <a href="/profile.php?id=1111&fref=fr_tab">Dave</a>
        ...         <a>Deleted user shoult not be extracted</a>
        ...         <a href="/friends/center/friends/?ppk=1&amp;
        ...             tid=u_0_0&amp;bph=1#friends_center_main">
        ...         <div id="m_more_friends">
        ...             <a href="/seeMoreLink">
        ...                 <span>See more friends</span>
        ...             </a>
        ...         </div>
        ...     </div>''')
        GenericResult(content=OrderedDict([('friends', OrderedDict([\
('username1?fref=fr_tab&foo', 'Mark'), \
('profile.php?id=1111&fref=fr_tab', 'Dave')]))]), \
see_more_links=['/seeMoreLink'])

        >>> FacebookSoupParser().parse_friends_page('''
        ...     <div id="objects_container">
        ...         <a href="/privacyx/selector/">
        ...         <a href="/friends/center/friends/?ppk=1&amp;
        ...             tid=u_0_0&amp;bph=1#friends_center_main">
        ...     </div>''')
        GenericResult(content=OrderedDict([('friends', OrderedDict())]), \
see_more_links=[])

        >>> FacebookSoupParser().parse_friends_page('''
        ...     <div id="objects_container">
        ...     </div>''')
        GenericResult(content=OrderedDict([('friends', OrderedDict())]), \
see_more_links=[])

        >>> FacebookSoupParser().parse_friends_page("")

        >>> FacebookSoupParser().parse_friends_page('''
        ...     <input name="login" type="submit" value="Log In">''')
        """

        soup = BeautifulSoup(content, "lxml")

        main_soup = soup.find(id="objects_container")
        if not main_soup:

            logging.error(detect_error_type(content))
            return None

        friends_found = OrderedDict()
        links_soup = main_soup.find_all(
            "a",
            attrs={"href": re.compile(r"^/.*fref=fr_tab")})
        for link in links_soup:
            friends_found[link.attrs["href"][1:]] = \
                link.text

        result = OrderedDict()
        result["friends"] = friends_found

        see_more_links = []
        div_more = main_soup.find("div", id="m_more_friends")
        if div_more:
            more_link = div_more.find("a")
            if more_link:
                see_more_links.append(more_link.attrs["href"])

        return GenericResult(
            content=result, see_more_links=see_more_links)

    def parse_likes_page(self, content):
        """Extract information from the page showing the likes of a user.

        Returns a GenericResult, containing:
        - content: an OrderedDict mapping categories to likes, e.g.:
        ([('category1', OrderedDict([('link1', 'likeName1'), ...]), ...])
        - see_more_links: all the links that were found on the page to explore.

        >>> FacebookSoupParser().parse_likes_page('''
        ...     <div id="objects_container">
        ...         <div>
        ...             <h4>Music </h4>
        ...             <div><img src="cat1ImgUrl1"><div>
        ...                 <a href="/cat1Link1"><span>Item 1-1</span></a><br>
        ...                 <a href="/cat1BadLink1">Like</a>
        ...             </div></div>
        ...             <div id="m_more_item">
        ...                 <a href="/cat1SeeMoreLink">
        ...                 <span>See more</span></a>
        ...             </div>
        ...         </div>
        ...         <div>
        ...             <h4>Restaurants </h4>
        ...             <div><img src="cat2ImgUrl1"><div>
        ...                 <a href="/cat2Link1">
        ...                     <span>Item 2-1</span>
        ...                 </a><br>
        ...                 <a href="/cat2BadLink1">Like</a>
        ...             </div></div>
        ...         </div>
        ...         <div>
        ...             <div><h3>TV Programmes</h3></div>
        ...             <div><img src="cat3ImgUrl1"><div>
        ...                 <a href="/cat3Link1"><span>Item 3-1</span></a><br>
        ...                 <a href="/cat3BadLink1">Like</a>
        ...             </div></div>
        ...             <div><img src="cat3ImgUrl2"><div>
        ...                 <a href="/cat3Link2"><span>Item 3-2</span></a><br>
        ...                 <a href="/cat3BadLink2">Like</a>
        ...             </div></div>
        ...             <div id="m_more_item">
        ...                 <a href="/cat3SeeMoreLink">
        ...                 <span>See more</span></a>
        ...             </div>
        ...         </div>
        ...         <div>
        ...             <h4>Other </h4>
        ...             <div><img src="cat4ImgUrl1"><div>
        ...                 <a href="/cat4Link1"><span>Item 4-1</span></a><br>
        ...                 <a href="/cat4BadLink1">Like</a>
        ...             </div></div>
        ...             <div><img src="cat4ImgUrl2"><div>
        ...                 <a href="/cat4Link2"><span>Item 4-2</span></a><br>
        ...                 <a href="/cat4BadLink2">Like</a>
        ...             </div></div>
        ...             <div id="m_more_item">
        ...                 <a href="/cat4SeeMoreLink">
        ...                 <span>See more</span></a>
        ...             </div>
        ...         </div>
        ...     </div>''')
        GenericResult(content=OrderedDict([\
('Music', OrderedDict([('cat1Link1', 'Item 1-1')])), \
('Restaurants', OrderedDict([('cat2Link1', 'Item 2-1')])), \
('TV Programmes', OrderedDict([('cat3Link1', 'Item 3-1'), \
('cat3Link2', 'Item 3-2')])), \
('Other', OrderedDict([('cat4Link1', 'Item 4-1'), \
('cat4Link2', 'Item 4-2')]))]), \
see_more_links=['/cat1SeeMoreLink', '/cat3SeeMoreLink', '/cat4SeeMoreLink'])

        >>> FacebookSoupParser().parse_likes_page('''
        ...     <div id="objects_container">
        ...         <div title="Films"><h2>Films</h2></div>
        ...         <div id="root" role="main"><div id="timelineBody"">
        ...         <div>
        ...             <h4>Likes </h4>
        ...             <div><img src="cat1ImgUrl1"><div>
        ...                 <a href="/cat1Link1"><span>Item 1-1</span></a><br>
        ...                 <a href="/cat1BadLink1">Like</a>
        ...             </div></div>
        ...             <div><img src="cat1ImgUrl2"><div>
        ...                 <a href="/cat1Link2"><span>Item 1-2</span></a><br>
        ...                 <a href="/cat1BadLink2">Like</a>
        ...             </div></div>
        ...         </div>
        ...         </div>
        ...     </div>''')
        GenericResult(content=OrderedDict([\
('Films', OrderedDict([('cat1Link1', 'Item 1-1'), \
('cat1Link2', 'Item 1-2')]))]), \
see_more_links=[])

        >>> FacebookSoupParser().parse_likes_page('''
        ...     <div id="objects_container">
        ...     </div>''')
        GenericResult(content=OrderedDict(), see_more_links=[])

        >>> FacebookSoupParser().parse_likes_page("")

        >>> FacebookSoupParser().parse_likes_page('''
        ...     <input name="login" type="submit" value="Log In">''')
        """

        soup = BeautifulSoup(content, "lxml")

        main_soup = soup.find(id="objects_container")
        if not main_soup:

            logging.error(detect_error_type(content))
            return None

        see_more_links = []
        result = OrderedDict()

        main_category = None
        main_category_soup = main_soup.find("h2")
        if main_category_soup:
            main_category = main_category_soup.text

        category_soup = main_soup.find_all(re.compile("^h[34]$"))
        for category in category_soup:
            category_name = category.text.strip()
            if main_category:  # e.g. for Films, category_name is Likes
                category_name = main_category

            result[category_name] = OrderedDict()

            parent_tag = None
            if category.name == "h4":
                parent_tag = category.parent
            else:
                parent_tag = category.parent.parent

            link_soup = parent_tag.find_all(
                "a", attrs={"href": re.compile(r"^/.*")})
            for link in link_soup:
                if link.text.strip() == "See more":
                    see_more_links.append(link.attrs["href"])
                elif link.text != "Like":
                    result[category_name][link.attrs["href"][1:]] = \
                        link.text.strip()

        return GenericResult(
            content=result, see_more_links=see_more_links)

    def parse_mutual_friends_page(self, content):
        """Extract information from a mutual friends page.

        Returns an OrderedDict([('username1', {'name': 'name1'}), ...]) mapping
        usernames to names.

        >>> FacebookSoupParser().parse_mutual_friends_page('''
        ...     <div id="objects_container">
        ...         <a href="/some/other/link">
        ...         <a href="some/other?fref=fr_tab"></a>
        ...         <a href="/username.1?fref=fr_tab">Name 1</a>
        ...         <a href="/username.2?fref=fr_tab&refid=17">Name 2</a>
        ...         <div id="m_more_mutual_friends">
        ...             <a href="/seeMoreLink">
        ...                 <span>195 more mutual friends</span>
        ...             </a></div>
        ...     </div>''')
        GenericResult(content=OrderedDict([('mutual_friends', OrderedDict([\
('username.1?fref=fr_tab', 'Name 1'), \
('username.2?fref=fr_tab&refid=17', 'Name 2')]))]), \
see_more_links=['/seeMoreLink'])

        >>> FacebookSoupParser().parse_mutual_friends_page('''
        ...     <div id="objects_container">
        ...         <a href="/privacyx/selector/">
        ...         <a href="/friends/center/friends/?ppk=1&amp;
        ...             tid=u_0_0&amp;bph=1#friends_center_main">
        ...     </div>''')
        GenericResult(content=OrderedDict([('mutual_friends', \
OrderedDict())]), see_more_links=[])

        >>> FacebookSoupParser().parse_mutual_friends_page('''
        ...     <div id="objects_container">
        ...     </div>''')
        GenericResult(content=OrderedDict([('mutual_friends', \
OrderedDict())]), see_more_links=[])

        >>> FacebookSoupParser().parse_mutual_friends_page("")

        >>> FacebookSoupParser().parse_mutual_friends_page('''
        ...     <input name="login" type="submit" value="Log In">''')
        """

        soup = BeautifulSoup(content, "lxml")

        main_soup = soup.find(id="objects_container")
        if not main_soup:

            logging.error(detect_error_type(content))
            return None

        mutual_friends_found = OrderedDict()
        links_soup = main_soup.find_all(
            "a", attrs={"href": re.compile(r"^/.*\?fref=fr_tab")})
        for link in links_soup:
            mutual_friends_found[link.attrs["href"][1:]] = link.text

        result = OrderedDict()
        result["mutual_friends"] = mutual_friends_found

        see_more_links = []
        div_more = main_soup.find("div", id="m_more_mutual_friends")
        if div_more:
            more_link = div_more.find("a")
            if more_link:
                see_more_links.append(more_link.attrs["href"])

        return GenericResult(
            content=result, see_more_links=see_more_links)

    def parse_timeline_years_links(self, content):
        """
        >>> FacebookSoupParser().parse_timeline_years_links('''
        ...     <div id="tlFeed">
        ...         <a class="bn" href="badLink1">Mark</a>
        ...         <a href="link1">2010</a>
        ...         <a href="link2">2009</a>
        ...         <a class="bn" href="badLink2">Dave</a>
        ...     </div>''')
        ['link1', 'link2']
        >>> FacebookSoupParser().parse_timeline_years_links('''
        ...     <div id="timelineBody">
        ...         <a class="bn" href="badLink1">Mark</a>
        ...         <a href="link1">2010</a>
        ...         <a href="link2">2009</a>
        ...         <a class="bn" href="badLink2">Dave</a>
        ...     </div>''')
        ['link1', 'link2']
        >>> FacebookSoupParser().parse_timeline_years_links('''
        ...     <div id="m_group_stories_container">
        ...         <a class="bn" href="badLink1">Mark</a>
        ...         <a href="link1">2010</a>
        ...         <a href="link2">2009</a>
        ...         <a class="bn" href="badLink2">Dave</a>
        ...     </div>''')
        ['link1', 'link2']
        >>> FacebookSoupParser().parse_timeline_years_links('''
        ...     <div id="m_group_stories_container">
        ...         <a href="badLink">Not a 2010 link to catch</a>
        ...     </div>''')
        []
        >>> FacebookSoupParser().parse_timeline_years_links('''
        ...     <input name="login" type="submit" value="Log In">''')
        []
        """

        soup = BeautifulSoup(content, "lxml")

        links_found = []

        main_soup = soup.find(
            id=["tlFeed", "timelineBody", "m_group_stories_container"])
        if not main_soup:

            logging.error(detect_error_type(content))
            return links_found

        links_soup = main_soup.find_all('a')
        for link in links_soup:
            if "href" in link.attrs:
                year_found = re.match(r'^\d{4}$', link.text)
                if year_found:
                    links_found.append(link.attrs["href"])

        return links_found

    def parse_post(self, soup):
        """
        >>> FacebookSoupParser().parse_post(BeautifulSoup('''
        ...   <article>
        ...     <div>
        ...       <a href="/username1?refid=18=nf&amp;foo">User 1</a>
        ...       <span>Some text</span>
        ...       <a href="/username2?refid=18">User 2</a>
        ...       <a href="/username2?refid=18">User 2 again!</a>
        ...       <a href="/profile.php?id=3333&amp;refid=18">User 3</a>
        ...     </div>
        ...     <div>
        ...       <a href="/page/photos/123/?type=3&amp;source=48&amp;\
refid=18"></a>
        ...       <a href="/story.php?story_fbid=123&amp;id=4&amp;\
refid=18"></a>
        ...       <a href="/browse/users/?ids=4444%2C5555&amp;">
        ...       </a>
        ...       <span>Some more</span>
        ...       <a href="/profile.php?id=666666&amp;refid=17">
        ...         Location
        ...       </a>
        ...       <span>.</span>
        ...     </div>
        ...     <div data-ft="foo">
        ...       <abbr>13 May 2008 at 10:02</abbr>
        ...       <span id="like_151">
        ...         <a aria-label="10 reactions, including Like and \
Love" href="/link1">10</a>
        ...         <a href="/link2">React</a>
        ...       </span>
        ...       <a href="/link3">12 Comments</a>
        ...       <a href="https://m.facebook.com/fu">Full Story</a>
        ...     </div>
        ...   </article>''', 'lxml'))
        OrderedDict([('post_id', 151), \
('content', 'User 1 Some text User 2 User 2 again! \
User 3 - Some more Location.'), \
('participants', ['username1', 'username2', 'profile.php?id=3333', \
'4444', '5555']), \
('date', '2008-05-13 10:02:00'), \
('date_org', '13 May 2008 at 10:02'), ('like_count', 10), \
('comment_count', 12), \
('story_link', 'https://m.facebook.com/fu')])

        >>> FacebookSoupParser().parse_post(BeautifulSoup('''
        ...     <article>
        ...         <div>
        ...             Some text
        ...         </div>
        ...         <div data-ft="foo">
        ...             <abbr>13 May 2008 at 10:02</abbr>
        ...             <span id="like_151">
        ...                 <a aria-label="114K reactions, including \
Like, Love and Wow" href="/link1">114,721</a>
        ...                 <a href="/link2">React</a>
        ...             </span>
        ...             <a href="/link3">2,746 Comments</a>
        ...         </div>
        ...     </article>''', 'lxml'))
        OrderedDict([('post_id', 151), ('content', 'Some text'), \
('participants', []), \
('date', '2008-05-13 10:02:00'), \
('date_org', '13 May 2008 at 10:02'), ('like_count', 114721), \
('comment_count', 2746), ('story_link', '')])

        >>> FacebookSoupParser().parse_post(BeautifulSoup('''
        ...     <article>
        ...         <div>
        ...             Some text
        ...         </div>
        ...         <div data-ft="foo">
        ...             <abbr>14 May 2008 at 10:02</abbr>
        ...             <span id="like_152">
        ...                 <a href="/link1">Like</a>
        ...                 <a href="/link2">React</a>
        ...             </span>
        ...             <a href="/link3">Comment</a>
        ...         </div>
        ...     </article>''', 'lxml'))
        OrderedDict([('post_id', 152), ('content', 'Some text'), \
('participants', []), \
('date', '2008-05-14 10:02:00'), \
('date_org', '14 May 2008 at 10:02'), ('like_count', 0), \
('comment_count', 0), ('story_link', '')])

        >>> FacebookSoupParser().parse_post(BeautifulSoup('''
        ...     <article>
        ...     </article>''', 'lxml'))

        >>> FacebookSoupParser().parse_post(BeautifulSoup('''
        ...     <article>
        ...         <div data-ft="foo">
        ...             <abbr>14 May 2008 at 10:02</abbr>
        ...         </div>
        ...     </article>''', 'lxml'))
        """

        # doctests only: remove generated 'html' tag
        if soup.name != "article":
            soup = soup.article

        participants_found = []
        content = []
        if not soup:
            return None
        for child in soup.children:
            if hasattr(child, 'attrs'):
                if "data-ft" in child.attrs:
                    break
                link_soup = child.find_all(href=re.compile("^/.*"))
                for link in link_soup:
                    link_found = link.attrs["href"][1:]
                    if "/profile.php" in link_found:
                        link_found = link_found.split("/profile.php?id=")[1]
                        ids = link_found.split("&")[0]
                        participants_found.append(ids)
                    else:
                        id_found = link_found.split("&refid=18")[0]
                        id_found = id_found.split("?refid=18")[0]
                        id_found = id_found.split("?lst")[0]
                        id_found = id_found.split("&fref")[0]
                        id_found = id_found.split("&lst")[0]
                        if id_found != link_found and \
                            id_found not in participants_found and \
                            '/photos/' not in id_found and \
                            'story.php?' not in id_found:
                            participants_found.append(id_found)

                sub_content = []
                for s in child.strings:
                    stripped_s = s.strip()
                    if stripped_s:
                        sub_content.append(stripped_s)
                content.append(" ".join(sub_content))
        content_string = " - ".join(content)
        content_string = content_string.replace(" .", ".")

        date_tag = soup.find("abbr")
        if not date_tag:
            logging.info("Skipping original article shared.")
            return None
        date_org = date_tag.text
        date = str(model.parse_date(date_org))

        span_tag = soup.find(id=re.compile(r"like_\d+"))
        if not span_tag:
            logging.info("Skipping article - no link for likes found.")
            return None
        article_id = int(re.findall(r'\d+', span_tag.attrs["id"])[0])
        h3_element = soup.find('h3')
        withs = []
        location = {}
        with_exist = False
        location_exist = False
        for child in h3_element.children:
            if child.name == "span": # no additional info
                break
            
                
            if with_exist == True:
                if child.name == "a":
                    with_element = child
                else:
                    with_element = child.find('a')
                with_name = with_element.text
                with_url = with_element.attrs['href'].split('&')[0]
                withs.append({'name': with_name, 'url': with_url})
                with_exist = False
            if location_exist == True:
                location['name'] = child.find('a').text
                location['url'] = child.find('a').attrs['href'].split('&')[0]
                location_exist = False
            if isinstance(child, NavigableString):
                text = child
            else:
                text = child.text
            if "with" in (text.strip().lower().split(" ")) or ("and" in text.strip().lower().split(" ")):
                with_exist = True
            if "at" in text.strip().lower().split(" "):
                location_exist = True


        like_count = 0
        reaction_link = span_tag.find(
            'a', attrs={"aria-label": re.compile(r"reaction")})
        if reaction_link:
            like_count = int(reaction_link.text.replace(",", ""))

        comment_count = 0
        comment_link = soup.find("a", string=re.compile(r"\d+ Comment"))
        if comment_link:
            comment_count = int(
                comment_link.text.split(" Comment")[0].replace(",", ""))

        full_story_link = ""
        full_story_soup = soup.find("a", string="Full Story")
        if full_story_soup and "href" in full_story_soup.attrs:
            full_story_link = full_story_soup.attrs["href"]

        return OrderedDict([
            ("post_id", article_id), ("content", content_string),
            ("location", location),
            ("participants", participants_found),
            ("date", date), ("date_org", date_org),
            ("like_count", like_count), ("comment_count", comment_count),
            ("story_link", full_story_link)])

    def parse_timeline_page(self, content):
        """
        >>> FacebookSoupParser().parse_timeline_page('''
        ...     <div id="tlFeed">
        ...         <article>
        ...             <div data-ft="foo">
        ...                 <abbr>13 May 2008 at 10:02</abbr>
        ...                 <span id="like_151"></span>
        ...             </div>
        ...         </article>
        ...         <article>
        ...             <div data-ft="foo">
        ...                 <abbr>13 May 2008 at 10:25</abbr>
        ...                 <span id="like_152"></span>
        ...             </div>
        ...         </article>
        ...         <div>
        ...             <a href="/show_more_link">Show more</a>
        ...         </div>
        ...     </div>''')
        TimelineResult(articles=OrderedDict([\
(151, OrderedDict([('post_id', 151), ('content', ''), \
('participants', []), \
('date', '2008-05-13 10:02:00'), \
('date_org', '13 May 2008 at 10:02'), ('like_count', 0), \
('comment_count', 0), ('story_link', '')])), \
(152, OrderedDict([('post_id', 152), ('content', ''), \
('participants', []), \
('date', '2008-05-13 10:25:00'), \
('date_org', '13 May 2008 at 10:25'), ('like_count', 0), \
('comment_count', 0), ('story_link', '')]))]), \
show_more_link='/show_more_link')
        >>> FacebookSoupParser().parse_timeline_page('''
        ...     <div id="timelineBody">
        ...         <article>
        ...             <article>
        ...             </article>
        ...             <div data-ft="foo">
        ...                 <abbr>13 May 2008 at 10:02</abbr>
        ...                 <span id="like_151"></span>
        ...             </div>
        ...         </article>
        ...     </div>''')
        TimelineResult(articles=OrderedDict([\
(151, OrderedDict([('post_id', 151), ('content', ''), \
('participants', []), \
('date', '2008-05-13 10:02:00'), \
('date_org', '13 May 2008 at 10:02'), ('like_count', 0), \
('comment_count', 0), ('story_link', '')]))]), show_more_link='')
        >>> FacebookSoupParser().parse_timeline_page('''
        ...     <div id="m_group_stories_container">
        ...         <article>
        ...             <div data-ft="foo">
        ...                 <abbr>13 May 2008 at 10:02</abbr>
        ...                 <span id="like_151"></span>
        ...             </div>
        ...         </article>
        ...     </div>''')
        TimelineResult(articles=OrderedDict([\
(151, OrderedDict([('post_id', 151), ('content', ''), \
('participants', []), \
('date', '2008-05-13 10:02:00'), \
('date_org', '13 May 2008 at 10:02'), ('like_count', 0), \
('comment_count', 0), ('story_link', '')]))]), show_more_link='')
        >>> FacebookSoupParser().parse_timeline_page('''
        ...     <div id="structured_composer_async_container">
        ...         <article>
        ...             <div data-ft="foo">
        ...                 <abbr>13 May 2008 at 10:02</abbr>
        ...                 <span id="like_151"></span>
        ...             </div>
        ...         </article>
        ...     </div>''')
        TimelineResult(articles=OrderedDict([\
(151, OrderedDict([('post_id', 151), ('content', ''), \
('participants', []), \
('date', '2008-05-13 10:02:00'), \
('date_org', '13 May 2008 at 10:02'), ('like_count', 0), \
('comment_count', 0), ('story_link', '')]))]), show_more_link='')
        >>> FacebookSoupParser().parse_timeline_page('''
        ...     <input name="login" type="submit" value="Log In">''')
        """
        soup = BeautifulSoup(content, "lxml")

        main_soup = soup.find(
            id=[
                "tlFeed", "timelineBody", "m_group_stories_container",
                "structured_composer_async_container"])
        if not main_soup:

            logging.error(detect_error_type(content))
            return None

        articles_found = OrderedDict()
        articles_soup = main_soup.find_all("article")
        for article in articles_soup:
            post = self.parse_post(article)
            if post:
                logging.info(
                    "Found post: {0}".format(post))
                # The same post_id might be returned several times,
                # e.g. when adding photos to albums. Overwrite, since
                # only the date will change.
                articles_found[post["post_id"]] = post

        show_more_link_tag = soup.find(
            "a", string=["Show more", "See more posts"])
        link_found = ""
        if show_more_link_tag and "href" in show_more_link_tag.attrs:
            link_found = show_more_link_tag.attrs["href"]

        return TimelineResult(
            articles=articles_found, show_more_link=link_found)

    def parse_reaction_page(self, content):
        """
        >>> FacebookSoupParser().parse_reaction_page('''
        ...     <div id="objects_container">
        ...         <a role="button" href="/ufi/badLink">All 2</a>
        ...         <a class="bn" href="/username1">Mark</a>
        ...         <a class="bn" href="bad/Link1">Mark</a>
        ...         <a class="bn" href="/username2">Paul</a>
        ...         <a href="/a/mobile/friends/add_friend.php?id=123"></a>
        ...         <a class="bn" href="badLink2">Dave</a>
        ...         <a href="/ufi/reaction/profile/browser/fetch/?"></a>
        ...         <div>
        ...             <a href="/ufi/reaction/link"><span>See more</span></a>
        ...         </div>
        ...     </div>''')
        ReactionResult(likers=['username1', 'username2'], \
see_more_link='/ufi/reaction/link')
        >>> FacebookSoupParser().parse_reaction_page('''
        ...     <div id="objects_container">
        ...         <span>The page you requested cannot be displayed</span>
        ...         <a href="/home.php?rand=852723744">Back to home</a>
        ...     </div>''')
        ReactionResult(likers=[], see_more_link=None)
        >>> FacebookSoupParser().parse_reaction_page('''
        ...     <input name="login" type="submit" value="Log In">''')
        """

        soup = BeautifulSoup(content, "lxml")

        usernames_found = []

        main_soup = soup.find(id="objects_container")
        if not main_soup:

            logging.error(detect_error_type(content))
            return None

        links_soup = main_soup.find_all(href=re.compile("^/.*"))
        invalid_links = ["add_friend.php", "ufi/reaction", "home.php?"]
        for link in links_soup:
            if "role" not in link.attrs and \
               "href" in link.attrs:

                username = link.attrs["href"][1:]

                is_invalid = False
                for invalid_link in invalid_links:
                    if invalid_link in username:
                        is_invalid = True
                        break

                if username and not is_invalid:
                    usernames_found.append(username)

        see_more_link_tag = main_soup.find("a", string="See more")
        link_found = None
        if see_more_link_tag and "href" in see_more_link_tag.attrs:
            link_found = see_more_link_tag.attrs["href"]

        return ReactionResult(
            likers=usernames_found, see_more_link=link_found)
