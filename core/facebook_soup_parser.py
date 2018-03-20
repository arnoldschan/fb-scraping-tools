from bs4 import BeautifulSoup
from collections import namedtuple
from collections import OrderedDict

import logging
import re


TimelineResult = namedtuple('TimelineResult', ['articles', 'show_more_link'])


class FacebookSoupParser:

    def parse_about_page(self, content):
        """Extract information from the mobile version of the about page.

        Returns an OrderedDict([('Name', ''), ...]).

        Keys are added only if the fields were found in the about page.

        >>> FacebookSoupParser().parse_about_page('''
        ...    <title id="pageTitle">Mark Zuckerberg</title>
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ... ''')["Name"]
        'Mark Zuckerberg'
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div class="dc dd dq" title="Birthday">
        ...             <div class="dv">14 May 1984</div>
        ...         </div>
        ...    </div>
        ...    ''')["Birthday"]
        '14 May 1984'
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div class="dc dd dq" title="Birthday">
        ...             <div class="dv">14 May 1984</div>
        ...         </div>
        ...    </div>
        ...    ''')["Year of birth"]
        1984
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div class="dc dd dq" title="Birthday">
        ...             <div class="dv">14 May</div>
        ...         </div>
        ...    </div>
        ...    ''')["Day and month of birth"]
        '14 May'
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div class="_5cds _2lcw _5cdu" title="Gender">
        ...             <div class="_5cdv r">Male</div>
        ...         </div>
        ...    </div>
        ...    ''')["Gender"]
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
        ...    ''')["Gender"]
        'Male'
        >>> FacebookSoupParser().parse_about_page('''
        ...    <a href="/mark?v=timeline&amp;lst=1%3A4%3A2">Timeline</a>'
        ...    <div class="timeline aboutme">
        ...         <div id="relationship"><div class="cq">''' + \
                    'Relationship</div><div class="cu do cv">' + \
                    'Married to <a class="bu" href="/someone">Someone</a>' + \
                    ' since 14 March 2010</div></div>' + '''
        ...    </div>
        ...    ''')["Relationship"]
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
        ...    </div>''')["Work"]
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
        ...    </div>''')["Education"]
        '1st education'
        >>> FacebookSoupParser().parse_about_page('''
        ...     <a href="/mark?v=timeline&amp;lst=1%3A12345%3A2">
        ...         Timeline
        ...     </a>''')["id"]
        12345
        """
        soup = BeautifulSoup(content, "lxml")

        user_info = OrderedDict()

        name_tag = soup.find("title")
        if name_tag:
            user_info["Name"] = name_tag.text

        timeline_tag = soup.find(href=re.compile(
            "^/.*\?v=timeline.lst=\d+%3A\d+%3A"))
        if not timeline_tag:
            logging.error("Failed to extract id.")
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
                user_info[tag] = found_tag.text. \
                    replace(tag, "").replace("\n", "").replace(" · Edit", "")

        if "Birthday" in user_info:
            parsed_birthday = user_info["Birthday"]
            if parsed_birthday.count(" ") != 2:
                user_info["Day and month of birth"] = parsed_birthday
                del user_info["Birthday"]
            else:
                user_info["Day and month of birth"] = " ".join(
                    parsed_birthday.split(" ")[0:2])
                user_info["Year of birth"] = parsed_birthday.split(" ")[-1]

        if "Year of birth" in user_info:
            user_info["Year of birth"] = int(user_info["Year of birth"])

        institution_tags = ["work", "education"]
        for institution_tag in institution_tags:
            found_tag = soup.find("div", attrs={"id": institution_tag})
            if found_tag:
                found_img_tag = found_tag.find("img")
                if found_img_tag and "alt" in found_img_tag.attrs:
                    user_info[institution_tag.capitalize()] = \
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
                    user_info["Relationship"] = relationship_choice
                    break

        return user_info

    def parse_friends_page(self, content):
        """Extract information from the mobile version of the friends page.

        JavaScript has to be disabled when fetching the page, otherwise, the
        content returned by requests does not contain the UIDs.

        Returns an OrderedDict([('111', {'Name': ''}), ...]) mapping user ids
        to names.

        >>> FacebookSoupParser().parse_friends_page('''
        ...     <div id="friends_center_main">
        ...         <a href="/privacyx/selector/">
        ...         <a class="bn" href="/friends/hovercard/mbasic/?
        ...             uid=111&amp;redirectURI=https%3A%2F%2Fm.facebook.com
        ...         ">Mark</a>
        ...         <a class="bn" href="/friends/hovercard/mbasic/?
        ...             uid=222&amp;redirectURI=https%3A%2F%2Fm.facebook.com
        ...         ">Dave</a>
        ...         <a href="/friends/center/friends/?ppk=1&amp;
        ...             tid=u_0_0&amp;bph=1#friends_center_main">
        ...     </div>''')
        OrderedDict([('111', {'Name': 'Mark'}), ('222', {'Name': 'Dave'})])
        >>> FacebookSoupParser().parse_friends_page('''
        ...     <div id="friends_center_main">
        ...         <a href="/privacyx/selector/">
        ...         <a href="/friends/center/friends/?ppk=1&amp;
        ...             tid=u_0_0&amp;bph=1#friends_center_main">
        ...     </div>''')
        OrderedDict()
        >>> FacebookSoupParser().parse_friends_page('''
        ...     <div id="friends_center_main">
        ...     </div>''')
        OrderedDict()
        >>> FacebookSoupParser().parse_friends_page("")
        OrderedDict()
        """

        soup = BeautifulSoup(content, "lxml")

        friends_found = OrderedDict()

        main_soup = soup.find(id="friends_center_main")
        if not main_soup:
            logging.error("Failed to parse friends page")
            return friends_found

        links_soup = main_soup.find_all("a")
        for link in links_soup:
            if "href" in link.attrs:
                uid_found = re.findall(r'uid=\d+', link.attrs["href"])
                if uid_found:
                    friends_found[uid_found[0].replace("uid=", "")] =\
                        {"Name": link.text}

        return friends_found

    def parse_years_links_from_timeline_page(self, content):
        """
        >>> FacebookSoupParser().parse_years_links_from_timeline_page('''
        ...     <div id="tlFeed">
        ...         <a class="bn" href="badLink1">Mark</a>
        ...         <a href="link1">2010</a>
        ...         <a href="link2">2009</a>
        ...         <a class="bn" href="badLink2">Dave</a>
        ...     </div>''')
        ['link1', 'link2']
        >>> FacebookSoupParser().parse_years_links_from_timeline_page('''
        ...     <input name="login" type="submit" value="Log In">''')
        []
        """

        soup = BeautifulSoup(content, "lxml")

        links_found = []

        main_soup = soup.find(id="tlFeed")
        if not main_soup:

            login_found = soup.find("input", attrs={"name": "login"})
            if login_found:
                logging.error("Cookie expired or is invalid, login requested.")
            else:
                logging.error("Failed to parse timeline page")
            return links_found

        links_soup = main_soup.find_all('a')
        for link in links_soup:
            if "href" in link.attrs:
                year_found = re.findall(r'\d{4}', link.text)
                if year_found:
                    links_found.append(link.attrs["href"])

        return links_found

    def parse_timeline_page(self, content):
        """
        >>> FacebookSoupParser().parse_timeline_page('''
        ...     <div id="tlFeed">
        ...         <div role="article">
        ...             <abbr>13 May 2008 at 10:02</abbr>
        ...             <span id="like_1">
        ...                 <a href="/link1">Like</a>
        ...                 <a href="/badLink1">React</a>
        ...             </span>
        ...         </div>
        ...         <div role="article">
        ...             <abbr>13 May 2008 at 10:25</abbr>
        ...             <span id="like_2">
        ...                 <a href="/link2">Like</a>
        ...                 <a href="/badLink2">React</a>
        ...             </span>
        ...         </div>
        ...         <div>
        ...             <a href="/show_more_link">Show more</a>
        ...         </div>
        ...     </div>''')
        TimelineResult(articles=OrderedDict([(1, '13 May 2008 at 10:02'), \
(2, '13 May 2008 at 10:25')]), show_more_link='/show_more_link')
        >>> FacebookSoupParser().parse_timeline_page('''
        ...     <div id="tlFeed">
        ...         <div role="article">
        ...             <div role="article">
        ...             </div>
        ...             <abbr>13 May 2008 at 10:02</abbr>
        ...             <span id="like_1">
        ...                 <a href="/link1">Like</a>
        ...                 <a href="/badLink1">React</a>
        ...             </span>
        ...         </div>
        ...     </div>''')
        TimelineResult(articles=OrderedDict([(1, '13 May 2008 at 10:02')]), \
show_more_link='')
        >>> FacebookSoupParser().parse_timeline_page('''
        ...     <input name="login" type="submit" value="Log In">''')
        """

        soup = BeautifulSoup(content, "lxml")

        main_soup = soup.find(id="tlFeed")
        if not main_soup:

            login_found = soup.find("input", attrs={"name": "login"})
            if login_found:
                logging.error("Cookie expired or is invalid, login requested.")
            else:
                logging.error("Failed to parse timeline page")
            return None

        articles_found = OrderedDict()

        articles_soup = main_soup.find_all("div", attrs={"role": "article"})
        for article in articles_soup:

            abbr_tag = article.find("abbr")
            if not abbr_tag:
                logging.info("Skipping original article shared.")
                continue

            span_tag = article.find(id=re.compile("like_\d+"))
            if not span_tag:
                logging.info("Skipping article - no link for likes found.")
                continue

            article_id = int(re.findall(r'\d+', span_tag.attrs["id"])[0])

            if article_id in articles_found:
                # Can happen when adding photos to albums
                logging.info(
                    "Overriding date for article '{0}': "
                    "old date: '{1}' - new date: '{2}'".format(
                        article_id, articles_found[article_id], abbr_tag.text))
            articles_found[article_id] = abbr_tag.text

        show_more_link_tag = soup.find("a", string="Show more")
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
        ...     </div>''')
        ['username1', 'username2']
        >>> FacebookSoupParser().parse_reaction_page('''
        ...     <div id="objects_container">
        ...         <span>The page you requested cannot be displayed</span>
        ...         <a href="/home.php?rand=852723744">Back to home</a>
        ...     </div>''')
        []
        >>> FacebookSoupParser().parse_reaction_page('''
        ...     <input name="login" type="submit" value="Log In">''')
        """

        soup = BeautifulSoup(content, "lxml")

        usernames_found = []

        main_soup = soup.find(id="objects_container")
        if not main_soup:

            login_found = soup.find("input", attrs={"name": "login"})
            if login_found:
                logging.error("Cookie expired or is invalid, login requested.")
            else:
                logging.error("Failed to parse timeline page")
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

        return usernames_found
