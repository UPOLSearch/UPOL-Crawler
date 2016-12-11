import urllib.parse
from crawler.urls import validator
from crawler.urls import url_tools


def is_page_wiki(soup):
    """Detect if page is wiki, from soup"""

    meta_generators = soup.find_all('meta', {'name': 'generator'})

    for meta_generator in meta_generators:
        content = meta_generator['content']
        if "MediaWiki" in content:
            return True

    return False


def is_page_phpbb(soup):
    """Detect if page is phpBB, from soup"""
    return (soup.find('body', id='phpbb') is not None)


def base_url(soup, url):
    """Get base url from page (check if base html tag exists)"""
    base_url = url
    base_tag = soup.find_all('base', href=True)

    if len(base_tag) > 0:
        base_url = base_tag[0]['href']

    return base_url


def wiki_page(soup):
    """Parse wiki page and return valid links"""

    content_div = soup.find('div', id='content')

    for div in content_div.find_all('div', {'class': 'printfooter'}):
        div.decompose()

    links_tmp = content_div.find_all('a', href=True)
    links = set()

    for link in links_tmp:
        if validator.validate_wiki(link['href']):
            links.add(link)

    return links


def phpBB_page(soup):
    """Parse phpBB page and return valid links"""

    content_div = soup.find('div', id='page-body')

    for p in content_div.find_all('p', {'class': 'jumpbox-return'}):
        p.decompose()

    links_tmp = content_div.find_all('a', href=True)
    links = set()

    for link in links_tmp:
        if validator.validate_phpbb(link['href']):
            links.add(link)

    return links


def link_extractor(soup, url):
    """Extract all links from page"""

    if is_page_wiki(soup):
        return wiki_page(soup)

    elif is_page_phpbb(soup):
        return phpBB_page(soup)

    else:
        return set(soup.find_all('a', href=True))


def validated_page_urls(soup, url):
    """Parse page and return set of valid urls"""

    valid_urls = set()
    links_on_page = link_extractor(soup, url)
    page_base_url = base_url(soup, url)

    for link in links_on_page:
        link_url = link['href']

        if not url_tools.is_url_absolute(link_url):
            link_url = urllib.parse.urljoin(page_base_url, link_url)

        link_url = url_tools.clean(link_url)

        if validator.validate(link_url):
            valid_urls.add(link_url)

    return valid_urls
