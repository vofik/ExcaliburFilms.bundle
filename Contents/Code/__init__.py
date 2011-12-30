# ExcaliburFilms
import re

# URLS
EXC_BASEURL = 'http://www.excaliburfilms.com/'
EXC_SEARCH_MOVIES_YEAR = EXC_BASEURL + 'search/AdvancedSearch_Results.htm?searchWord=%s&year_in=%s&year_in_to=%s&studio_in=ALL&category_in=ALL&inmovies=No&TrailerMovies=No&x=57&y=16&fromSearchPage=YES'
EXC_SEARCH_MOVIES = EXC_BASEURL + 'search/AdvancedSearch_Results.htm?searchWord=%s&studio_in=ALL&category_in=ALL&inmovies=No&TrailerMovies=No&x=57&y=16&fromSearchPage=YES'
EXC_MOVIE_INFO = EXC_BASEURL + 'AdultDVD/%s'

titleFormats = r'DVD|Blu-Ray|BR|Combo|Pack'

def Start():
  HTTP.CacheTime = CACHE_1DAY
  HTTP.SetHeader('User-agent', 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.2; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0)')

class EXCAgent(Agent.Movies):
  name = 'Excalibur Films'
  languages = [Locale.Language.English]
  accepts_from = ['com.plexapp.agents.localmedia']
  primary_provider = True

  def search(self, results, media, lang):

    title = media.name
    if media.primary_metadata is not None:
      title = media.primary_metadata.title

    year = media.year
    if media.primary_metadata is not None:
      year = media.primary_metadata.year
      Log('year: ' + year)

    Log('searching for : ' + title)

    if title.startswith('The '):
      if title.count(':'):
        title = title.split(':',1)[0].replace('The ','',1) + ', The:' + title.split(':',1)[1]
      else:
        title = title.replace('The ','',1) + ', The'

    query = String.URLEncode(String.StripDiacritics(title.replace('-','')))
    if year is not None:
      searchUrl = EXC_SEARCH_MOVIES_YEAR % (query, year, year)
    else:
      searchUrl = EXC_SEARCH_MOVIES % query
      
    Log('search url: ' + searchUrl)

    searchResults = HTML.ElementFromURL(searchUrl)
    searchTitle = searchResults.xpath('//title')[0].text_content()
    if(re.match(r'Advanced Search', searchTitle)):
      years = searchResults.xpath(
        '//font[@class="Size12" and @color="Black" and re:match(text(), "\d+/\d+/\d+")]',
        namespaces={"re": "http://exslt.org/regular-expressions"})
      count = 0
      for movie in searchResults.xpath('//a[contains(@class,"searchTitle13")]'):
        curName = movie.text_content().strip()
        curID = movie.get('href').split('/',4)[4]
        year = years[count].text_content().strip(',. ')
        score = 100 - Util.LevenshteinDistance(title.lower(), curName.lower())
        if score >= 85:
          if curName.count(', The'):
            curName = 'The ' + curName.replace(', The','',1)
          if year:
            curName = curName + ' [' + year + ']'
          results.Append(MetadataSearchResult(id = curID, name = curName, score = score, lang = lang))
        count += 1
    else:
      curName = re.sub(titleFormats,'',searchTitle).strip(' .-+')
      curID = searchResults.xpath('//a[contains(@href, "mailto") and contains(@href, "AdultDVD")]')[0].get('href')
      curID = re.search(r'/([^\\/]*)$', curID, re.M).group(1)
      results.Append(MetadataSearchResult(id = curID, name = curName, score = 90, lang = lang))

    results.Sort('score', descending=True)

  def update(self, metadata, media, lang):
    html = HTML.ElementFromURL(EXC_MOVIE_INFO % metadata.id)

    metadata.title = re.sub(titleFormats,'',media.title).strip(' .-+')
    metadata.title = re.sub(r'\[\d+/\d+/\d+\]','',metadata.title).strip(' ')

    # Get Thumb and Poster
    try:
      img = html.xpath('//img[@height="300" and contains(@src, "DVD/reviews/images")]')[0]
      thumbUrl = img.get('src')
      thumb = HTTP.Request(thumbUrl)
      posterUrl = re.sub(r'([^\/]*).jpg',r'largemoviepic/\1.jpg', thumbUrl)
      metadata.posters[posterUrl] = Proxy.Preview(thumb)
    except: pass

    # Genre.
    try:
      metadata.genres.clear()
      genres = html.xpath('//table[@width="620"]//table[@width="620"]//a[contains(@href, "DVD/Categories")]')

      if len(genres) > 0:
        for genreLink in genres:
          genreName = genreLink.text_content().strip('\n')
          if len(genreName) > 0 and re.match(r'View Complete List', genreName) is None:
            metadata.genres.add(genreName)
    except: pass


    # Summary.
    try:
      metadata.summary = ""
      summary = html.xpath('//font[@color="000000"]/p')
      if len(summary) > 0:
        for paragraph in summary:
          metadata.summary = metadata.summary + paragraph.text_content().replace('&13;', '').strip('. \t\n\r"') + "\n\n"
        metadata.summary.strip('\n')
      else:
        metadata.summary = html.xpath('//font[@color="000000"]')[0].text_content().replace('&13;', '').strip(' \t\n\r"')
    except: pass

    # Release Date
    try:
      release_date = html.xpath('//a[contains(@href, "popUpYear")]')[0].text_content().strip()
      metadata.originally_available_at = Datetime.ParseDate(release_date).date()
      metadata.year = metadata.originally_available_at.year
    except: pass

    # Starring
    try:
      #starring = html.xpath('//a[contains(@class,"starLink2") and contains(@href, "/pornlist/")]')
      starring = html.xpath('//font[@class="starLink1"]')[0].text_content().split(',')
      metadata.roles.clear()
      for member in starring:
        role = metadata.roles.new()
        role.actor = member.replace('&#13;', '').strip('. \t\n\r')
        Log('Starring: ' + role.actor)
    except: pass

    # Director
    try:
      director = html.xpath('//a[@class="starLink" and contains(@href, "/directors/")]')[0].text_content().strip()
      metadata.directors.clear()
      metadata.directors.add(director)
    except: pass

    # Studio
    try:
      metadata.studio = html.xpath('//a[@class="starLink" and contains(@href, "/adultstudios/")]')[0].text_content().strip()
    except: pass
