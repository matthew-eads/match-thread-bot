import praw,urllib2,cookielib,re,logging,datetime
from collections import Counter
from time import sleep

# TO DO: 
# more stream sources
# manual inputs (delete thread)
# deal with incorrect matching of non-existent game (eg using "City", etc) - ie better way of finding matches (nearest neighbour?)
# more robust handling of errors

# every minute, check mail, create new threads, update all current threads

def login():
	try:
		f = open('login.txt')
		username,password,subreddit,user_agent = f.readline().split(':',4)
		r = praw.Reddit(user_agent)
		r.login(username,password)
		f.close()
		return r,subreddit
	except:
		print "Login error: please ensure 'login.txt' file exists in its correct form (check readme for more info)"
		sleep(10)

# save activeThreads
def saveData():
	f = open('active_threads.txt', 'w+')
	s = ''
	for data in activeThreads:
		matchID,t1,t2,thread_id,body,teamsDone = data
		s += matchID + '####' + t1 + '####' + t2 + '####' + thread_id + '####' + body + '####' + str(teamsDone) + '&&&&'
	s = s[0:-4] # take off last &&&&
	f.write(s.encode('utf8'))
	f.close()

# read saved activeThreads data	
def readData():
	f = open('active_threads.txt', 'a+')
	s = f.read().decode('utf8')
	info = s.split('&&&&')
	if info[0] != '':
		for d in info:
			[matchID,t1,t2,thread_id,body,teamsDone] = d.split('####')
			matchID = matchID.encode('utf8') # get rid of weird character at start - got to be a better way to do this...
			teamsDone = teamsDone == 'True' # convert to boolean
			data = matchID, t1, t2, thread_id, body, teamsDone
			activeThreads.append(data)
			logging.info("Active threads: %i - added %s vs %s", len(activeThreads), t1, t2)
			print "Active threads: " + str(len(activeThreads)) + " - added " + t1 + " vs " + t2
	f.close()

def findGoalSite(team1, team2):
	# search for each word in each team name in goal.com's fixture list, return most frequent result
	hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive'}
	t1 = team1.split()
	t2 = team2.split()
	linkList = []
	fixAddress = "http://www.goal.com/en-us/live-scores"
	req = urllib2.Request(fixAddress, headers=hdr)
	fixWebsite = urllib2.urlopen(req)
	fix_html = fixWebsite.read()
	links = re.findall('/en-us/match/(.*?)"', fix_html)
	for link in links:
		for word in t1:
			if link.find(word.lower()) != -1:
				linkList.append(link)
		for word in t2:
			if link.find(word.lower()) != -1:
				linkList.append(link)		
	counts = Counter(linkList)
	if counts.most_common(1) != []:
		mode = counts.most_common(1)[0]
		return mode[0]
	else:
		return 'no match'
		
def getLineUps(matchID):
	# try to find line-ups (404 if line-ups not on goal.com yet)
	try:
		hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
		   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
		   'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
		   'Accept-Encoding': 'none',
		   'Accept-Language': 'en-US,en;q=0.8',
		   'Connection': 'keep-alive'}
		lineAddress = "http://www.goal.com/en-us/match/" + matchID + "/lineups"
		req = urllib2.Request(lineAddress, headers=hdr)
		lineWebsite = urllib2.urlopen(req)
		line_html_enc = lineWebsite.read()
		line_html = line_html_enc.decode("utf8")

		delim = '<ul class="player-list">'
		split = line_html.split(delim) # [0]:nonsense [1]:t1 XI [2]:t2 XI [3]:t1 subs [4]:t2 subs + managers

		managerDelim = '<div class="manager"'
		split[4] = split[4].split(managerDelim)[0] # managers now excluded
		
		team1Start = re.findall('<span class="name">(.*?)<',split[1],re.DOTALL)
		team2Start = re.findall('<span class="name">(.*?)<',split[2],re.DOTALL)	
		team1Sub = re.findall('<span class="name">(.*?)<',split[3],re.DOTALL)
		team2Sub = re.findall('<span class="name">(.*?)<',split[4],re.DOTALL)

		# if no players found, ie TBA
		if team1Start == []:
			team1Start = ["TBA"]
		if team1Sub == []:
			team1Sub = ["TBA"]
		if team2Start == []:
			team2Start = ["TBA"]
		if team2Sub == []:
			team2Sub = ["TBA"]
		return team1Start,team1Sub,team2Start,team2Sub
		
	except urllib2.HTTPError:
		team1Start = ["TBA"]
		team1Sub = ["TBA"]
		team2Start = ["TBA"]
		team2Sub = ["TBA"]
		return team1Start,team1Sub,team2Start,team2Sub

# check if match is finished - search for "FT"
def isMatchComplete(matchID):
	hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive'}
	lineAddress = "http://www.goal.com/en-us/match/" + matchID
	req = urllib2.Request(lineAddress, headers=hdr)
	lineWebsite = urllib2.urlopen(req)
	line_html = lineWebsite.read()
	status = re.findall('<div class="vs">(.*?)<',line_html,re.DOTALL)[0]
	return status == 'FT'			
	
# get venue, ref, lineups, etc from goal.com	
def getGDCinfo(matchID):
	hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive'}
	lineAddress = "http://www.goal.com/en-us/match/" + matchID
	req = urllib2.Request(lineAddress, headers=hdr)
	lineWebsite = urllib2.urlopen(req)
	line_html_enc = lineWebsite.read()
	line_html = line_html_enc.decode("utf8")

	# get "fixed" versions of team names (ie team names from goal.com, not team names from match thread request)
	team1fix = re.findall('<div class="home" .*?<h2>(.*?)<', line_html, re.DOTALL)[0]
	team2fix = re.findall('<div class="away" .*?<h2>(.*?)<', line_html, re.DOTALL)[0]
	
	if team1fix[-1]==' ':
		team1fix = team1fix[0:-1]
	if team2fix[-1]==' ':
		team2fix = team2fix[0:-1]	
	
	matchDone = isMatchComplete(matchID)
	ko = re.findall('<div class="match-header .*?</li>.*? (.*?)</li>', line_html, re.DOTALL)[0]
	
	venue = re.findall('<div class="match-header .*?</li>.*?</li>.*? (.*?)</li>', line_html, re.DOTALL)
	if venue != []:
		venue = venue[0]
	else:
		venue = '?'
		
	ref = re.findall('Referee: (.*?)</li>', line_html, re.DOTALL)
	if ref != []:
		ref = ref[0]	
	else:
		ref = '?'
		
	team1Start,team1Sub,team2Start,team2Sub = getLineUps(matchID)
		
	return (team1fix,team2fix,team1Start,team1Sub,team2Start,team2Sub,venue,ref,ko,matchDone)
	
def writeLineUps(body,t1,t2,team1Start,team1Sub,team2Start,team2Sub):
	body += '**LINE-UPS**\n\n**' + t1 + '**\n\n'
	body += ", ".join(x for x in team1Start) + ".\n\n"
	body += '**Subs:** '
	body += ", ".join(x for x in team1Sub) + ".\n\n^____________________________\n\n"
	
	body += '**' + t2 + '**\n\n'
	body += ", ".join(x for x in team2Start) + ".\n\n"
	body += '**Subs:** '
	body += ", ".join(x for x in team2Sub) + "."
	return body
	
def grabEvents(matchID):
	hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive'}
	lineAddress = "http://www.goal.com/en-us/match/" + matchID + "/live-commentary"
	req = urllib2.Request(lineAddress, headers=hdr)
	lineWebsite = urllib2.urlopen(req)
	line_html_enc = lineWebsite.read()
	line_html = line_html_enc.decode("utf8")
	
	body = ""
	split = line_html.split('<ul class="commentaries') # [0]:nonsense [1]:events
	events = split[1].split('<li data-event-type="')
	events = events[1:]
	
	# goal.com's full commentary tagged as "action" - ignore these
	# will only report goals (+ penalties, own goals), yellows, reds, subs - not sure what else goal.com reports
	for text in events:
		type = re.findall('(.*?)"',text,re.DOTALL)[0]
		if type.lower() == 'goal' or type.lower() == 'penalty-goal' or type.lower() == 'own-goal' or type.lower() == 'yellow-card' or type.lower() == 'red-card' or type.lower() == 'substitution':
			time = re.findall('<div class="time">\n?(.*?)<',text,re.DOTALL)[0]
			time = time[:-1] # goal.com leaves a space at the end
			info = '**' + time + '** '
			if type.lower() == 'goal' or type.lower() == 'penalty-goal':
				info += '[](//#ball) ' + re.findall('<div class="text">\n?(.*?)<',text,re.DOTALL)[0]
			if type.lower() == 'own-goal':
				info += '[](//#red-ball) ' + re.findall('<div class="text">\n?(.*?)<',text,re.DOTALL)[0]
			if type.lower() == 'yellow-card':
				info += '[](//#yellow) ' + re.findall('<div class="text">\n?(.*?)<',text,re.DOTALL)[0]
			if type.lower() == 'red-card':
				info += '[](//#red) ' + re.findall('<div class="text">\n?(.*?)<',text,re.DOTALL)[0]
			if type.lower() == 'substitution':
				info += '[](//#sub) Substitution: [](//#down)' + re.findall('"sub-out">(.*?)<',text,re.DOTALL)[0]
				info += ' [](//#up)' + re.findall('"sub-in">(.*?)<',text,re.DOTALL)[0]
			body = info + '\n\n' + body
		
	return body
	
def findWiziwigID(team1,team2):
	hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive'}
	t1 = team1.split()
	t2 = team2.split()
	linkList = []
	fixAddress = "http://www.wiziwig.tv/competition.php?part=sports&discipline=football"
	req = urllib2.Request(fixAddress, headers=hdr)
	try:
		fixWebsite = urllib2.urlopen(req)
	except urllib2.HTTPError, e:
		logging.error("Couldn't access wiziwig streams for %s vs %s", team1,team2)
		return 'no match'
	fix_html = fixWebsite.read()
	
	for word in t1:
		links = re.findall('<td class="home">.*?>.*?' + word + '.*?\n.*?\n.*?\n.*?broadcast" href="(.*?)"', fix_html)
		for link in links:	
			linkList.append(link)
	for word in t2:
		links = re.findall('<td class="away">.*?>.*?' + word + '.*?\n.*?broadcast" href="(.*?)"', fix_html)
		for link in links:
			linkList.append(link)

	counts = Counter(linkList)
	if counts.most_common(1) != []:
		mode = counts.most_common(1)[0]
		return mode[0]
	else:
		logging.info("Couldn't find wiziwig streams for %s vs %s", team1,team2)
		return 'no match'
		
def findFirstrowID(team1,team2):
	t1 = team1.split()
	t2 = team2.split()
	linkList = []
	fixAddress = "http://gofirstrowus.eu/"
	fixWebsite = urllib2.urlopen(fixAddress)
	fix_html = fixWebsite.read()
	
	for word in t1:
		links = re.findall('<a> <img class="chimg" alt=".*?' + word + ".*?\n.*?Link 1'href='(.*?)'",fix_html)
		for link in links:	
			linkList.append(link)
	for word in t2:
		links = re.findall('<a> <img class="chimg" alt=".*?' + word + ".*?\n.*?Link 1'href='(.*?)'",fix_html)
		for link in links:
			linkList.append(link)

	counts = Counter(linkList)
	if counts.most_common(1) != []:
		mode = counts.most_common(1)[0]
		return mode[0]
	else:
		logging.info("Couldn't find firstrow streams for %s vs %s", team1,team2)
		return 'no match'

# nutjob is dead! Remove this method if it's not coming back		
def findNutjobID(team1,team2):
	hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive'}
	t1 = team1.split()
	t2 = team2.split()
	linkList = []
	fixAddress = "http://nutjob.eu/schedule.html"
	req = urllib2.Request(fixAddress, headers=hdr)
	try:
		fixWebsite = urllib2.urlopen(req)
	except urllib2.HTTPError, e:
		logging.error("Couldn't access nutjob streams for %s vs %s", team1,team2)
		return 'no match'
	fix_html = fixWebsite.read()
	
	for word in t1:
		links = re.findall('<p>.*?' + word + '.*?<a href="(.*?)"',fix_html)
		for link in links:	
			linkList.append(link)
	for word in t2:
		links = re.findall('<p>.*?' + word + '.*?<a href="(.*?)"',fix_html)
		for link in links:
			linkList.append(link)

	counts = Counter(linkList)
	if counts.most_common(1) != []:
		mode = counts.most_common(1)[0]
		return mode[0]
	else:
		logging.info("Couldn't find nutjob streams for %s vs %s", team1,team2)
		return 'no match'
	
def findVideoStreams(team1,team2):
	text = "**Got a stream? Post it here!**\n\n"
	
	wiziID = findWiziwigID(team1,team2)
	firstrowID = findFirstrowID(team1,team2)
	#nutjobID = findNutjobID(team1,team2)
	
	if wiziID != 'no match':
		text += '[wiziwig](http://www.wiziwig.tv' + wiziID + ')\n\n'
	if firstrowID != 'no match':
		text += '[FirstRow](http://gofirstrowus.eu' + firstrowID + ')\n\n'
	#if nutjobID != 'no match':
	#	text += '[nutjob](http://nutjob.eu/' + nutjobID + ')\n\n'

	text += "-------------------------\n\n"
	text += "*Hi, I'm a match thread bot. [Click here](http://www.reddit.com/r/soccer/comments/22ah8i/introducing_matchthreadder_a_bot_to_set_up_match/) to learn how to use me, or to check status updates on if/when I'll be down for maintenance.*"
	
	return text

def getTimes(ko):
	hour = ko[0:ko.index(':')]
	minute = ko[ko.index(':')+1:ko.index(':')+3]
	ampm = ko[ko.index(' ')+1:]
	hour_i = int(hour)
	min_i = int(minute)
	
	if (ampm == 'PM') and (hour_i != 12):
		hour_i += 12		
	if (ampm == 'AM') and (hour_i == 12):
		hour_i = 0	
	
	now = datetime.datetime.now()
	return (hour_i,min_i,now)
	
# create a new thread using provided teams	
def createNewThread(team1,team2):	
	site = findGoalSite(team1,team2)
	if site != 'no match':
		t1, t2, team1Start, team1Sub, team2Start, team2Sub, venue, ref, ko, matchDone = getGDCinfo(site)
		
		# don't create a thread if MatchThreadder already made it
		for d in activeThreads:
			matchID_at,t1_at,t2_at,id_at,body_at,teamsDone_at = d
			if t1 == t1_at:
				return 4,id_at
		
		# don't create a thread if the match is done (probably found the wrong match)
		if matchDone == True:
			return 3,''
		
		# don't create a thread if the match hasn't started yet
		hour_i, min_i, now = getTimes(ko)
		if now.hour < hour_i:
			return 2,''
		if (now.hour == hour_i) and (now.minute < min_i):
			return 2,''
			
		teamsDone = (team1Start[0]!="TBA") and (team1Sub[0]!="TBA") and (team2Start[0]!="TBA") and (team2Sub[0]!="TBA")
		
		vidcomment = findVideoStreams(team1,team2)
		title = 'Match Thread: ' + t1 + ' vs ' + t2
		thread = r.submit(subreddit,title,text='Updates soon')
		vidlink = thread.add_comment(vidcomment)
		
		short = thread.short_link
		id = short[15:].encode("utf8")
		redditstream = 'http://www.reddit-stream.com/comments/' + id 
		
		body = '**Venue:** ' + venue + '\n\n' + '**Referee:** ' + ref + '\n\n--------\n\n'
		body += '[](//#stream-big) **STREAMS**\n\n'
		body += '[Video streams](' + vidlink.permalink + ')\n\n'
		body += '[Reddit comments stream](' + redditstream + ')\n\n---------\n\n'
		body += '[](//#notes-big) ' 
		body = writeLineUps(body,t1,t2,team1Start,team1Sub,team2Start,team2Sub)
		
		body += '\n\n------------\n\n[](//#net-big) **MATCH EVENTS**\n\n'
		body += '**' + t1 + ' 0-0 ' + t2 + '**'
		
		thread.edit(body)
		data = site, t1, t2, id, body, teamsDone
		activeThreads.append(data)
		saveData()
		logging.info("Active threads: %i - added %s vs %s", len(activeThreads), t1, t2)
		print "Active threads: " + str(len(activeThreads)) + " - added " + t1 + " vs " + t2
		return 0,id
	else:
		return 1,''

# if the requester just wants a template		
def createMatchInfo(team1,team2):
	site = findGoalSite(team1,team2)
	if site != 'no match':
		t1, t2, team1Start, team1Sub, team2Start, team2Sub, venue, ref, ko, matchDone = getGDCinfo(site)
			
		teamsDone = (team1Start[0]!="TBA") and (team1Sub[0]!="TBA") and (team2Start[0]!="TBA") and (team2Sub[0]!="TBA")
		
		body = '**Venue:** ' + venue + '\n\n' + '**Referee:** ' + ref + '\n\n--------\n\n'
		body += '[](//#stream-big) **STREAMS**\n\n'
		body += '[Video streams](LINK-TO-STREAMS-HERE)\n\n'
		body += '[Reddit comments stream](LINK-TO-REDDIT-STREAM-HERE)\n\n---------\n\n'
		body += '[](//#notes-big) ' 
		body = writeLineUps(body,t1,t2,team1Start,team1Sub,team2Start,team2Sub)
		
		body += '\n\n------------\n\n[](//#net-big) **MATCH EVENTS**\n\n'
		body += '**' + t1 + ' 0-0 ' + t2 + '**'
		
		logging.info("Provided info for %s vs %s", t1, t2)
		print "Provided info for " + t1 + " vs " + t2
		return 0,body
	else:
		return 1,''

# default attempt to find teams: split input in half, left vs right	
def firstTryTeams(msg):
	t = msg.split()
	spl = t.__len__()/2
	t1 = t[0:spl]
	t2 = t[spl+1:]
	t1s = ''
	t2s = ''
	for word in t1:
		t1s += word + ' '
	for word in t2:
		t2s += word + ' '
	return [t1s,t2s]

# check for new mail, create new threads if needed
def checkAndCreate():
	delims = [' - ',' x ',' v ',' vs ']
	for msg in r.get_unread(unset_has_mail=True,update_user=True,limit=None):
		msg.mark_as_read()
		if msg.subject.lower() == 'match thread':
			teams = firstTryTeams(msg.body)
			for delim in delims:
				attempt = msg.body.split(delim,2)
				if attempt[0] != msg.body:
					teams = attempt
			threadStatus,thread_id = createNewThread(teams[0],teams[1])
			if threadStatus == 0: # thread created successfully
				msg.reply("[Here](http://www.reddit.com/r/" + subreddit + "/comments/" + thread_id + ") is a link to the thread you've requested. Thanks for using this bot!")
			if threadStatus == 1: # not found
				msg.reply("Sorry, I couldn't find info for that match. In the future I'll account for more matches around the world.")
			if threadStatus == 2: # before kickoff
				msg.reply("Please wait until kickoff to send me a thread request, just in case someone does end up making one themselves. Thanks!")
			if threadStatus == 3: # after kickoff - probably found the wrong match
				msg.reply("Sorry, I couldn't find info for that match. In the future I'll account for more matches around the world.")
			if threadStatus == 4: # thread already exists
				msg.reply("There is already a [match thread](http://www.reddit.com/r/" + subreddit + "/comments/" + thread_id + ") for that game. Join the discussion there!")	
		if msg.subject.lower() == 'match info':
			teams = firstTryTeams(msg.body)
			for delim in delims:
				attempt = msg.body.split(delim,2)
				if attempt[0] != msg.body:
					teams = attempt
			threadStatus,text = createMatchInfo(teams[0],teams[1])
			if threadStatus == 0: # successfully found info
				msg.reply("Below is the information for the match you've requested. There are gaps left for you to add in a link to a comment containing stream links and a link to the reddit-stream for the thread; if you don't want to include these, be sure to remove those lines.\n\nIf you're using [RES](http://redditenhancementsuite.com/), you can use the 'source' button below this message to copy/paste the exact formatting code. If you aren't, you'll have to add the formatting yourself.\n\n----------\n\n" + text)
			if threadStatus == 1: # not found
				msg.reply("Sorry, I couldn't find info for that match. In the future I'll account for more matches around the world.")


# update score, scorers
def updateScore(matchID, t1, t2):
	lineAddress = "http://www.goal.com/en-us/match/" + matchID
	lineWebsite = urllib2.urlopen(lineAddress)
	line_html_enc = lineWebsite.read()
	line_html = line_html_enc.decode("utf8")
	leftScore = re.findall('<div class="home-score">(.*?)<',line_html,re.DOTALL)[0]
	rightScore = re.findall('<div class="away-score">(.*?)<',line_html,re.DOTALL)[0]
	
	split1 = line_html.split('<div class="home"') # [0]:nonsense [1]:scores
	split2 = split1[1].split('<div class="away"') # [0]:home score [1]:away scores + nonsense
	split3 = split2[1].split('<div class="module') # [0]:away score [1]:nonsense
	
	leftScorers = re.findall('<a href="/en-us/people/.*?>(.*?)<',split2[0],re.DOTALL)
	rightScorers = re.findall('<a href="/en-us/people/.*?>(.*?)<',split3[0],re.DOTALL)
		
	text = '**' + t1 + ' ' + leftScore + '-' + rightScore + ' ' + t2 + '**\n\n'
	
	if leftScorers != []:
		text += "*" + t1 + " scorers: "
		for scorer in leftScorers:
			scorer.replace('&nbsp;',' ')
			text += scorer + ", "
		text = text[0:-2] + "*\n\n"
		
	if rightScorers != []:
		text += "*" + t2 + " scorers: "
		for scorer in rightScorers:
			scorer.replace('&nbsp;',' ')
			text += scorer + ", "
		text = text[0:-2] + "*"
		
	return text
		
# update all current threads			
def updateThreads():
	toRemove = []

	for data in activeThreads:
		index = activeThreads.index(data)
		matchID,team1,team2,thread_id,body,teamsDone = data
		thread = r.get_submission(submission_id = thread_id)
		
		# try to fill out remaining lineups
		if teamsDone != True:
			team1Start,team1Sub,team2Start,team2Sub = getLineUps(matchID)
			lineupIndex = body.index('**LINE-UPS**')
			bodyTilThen = body[0:lineupIndex]
			newbody = writeLineUps(bodyTilThen,team1,team2,team1Start,team1Sub,team2Start,team2Sub)
			newbody += '\n\n------------\n\n[](//#net-big) **MATCH EVENTS**\n\n'
			teamsDone = (team1Start[0]!="TBA") and (team1Sub[0]!="TBA") and (team2Start[0]!="TBA") and (team2Sub[0]!="TBA")
		else:
			eventsIndex = body.index('**MATCH EVENTS**')
			newbody = body[0:eventsIndex]
			newbody +=  '**MATCH EVENTS**\n\n'
			
		# update scorelines
		score = updateScore(matchID,team1,team2)
		newbody += score
		
		events = grabEvents(matchID)
		newbody += '\n\n' + events

		# save data
		if newbody != body:
			logging.info("Making edit to %s vs %s", team1,team2)
			print "Making edit to " + team1 + " vs " + team2
			thread.edit(newbody)
			saveData()
		newdata = matchID,team1,team2,thread_id,newbody,teamsDone
		activeThreads[index] = newdata
		
		# discard finished matches - search for "FT"
		if isMatchComplete(matchID):
			toRemove.append(newdata)
			
	for getRid in toRemove:
		activeThreads.remove(getRid)
		logging.info("Active threads: %i - removed %s vs %s", len(activeThreads), team1, team2)
		print "Active threads: " + str(len(activeThreads)) + " - removed " + getRid[1] + " vs " + getRid[2]
		saveData()
		
logging.basicConfig(filename='log.log',level=logging.INFO,format='%(asctime)s %(message)s')
logging.info("[STARTUP]")

r,subreddit = login()
readData()
activeThreads = []

running = True
while running:
	try:
		checkAndCreate()
		updateThreads()
		sleep(60)
	except KeyboardInterrupt:
		logging.info("[MANUAL SHUTDOWN]")
		running = False
	except praw.errors.APIException:
		print "API error, check log file"
		logging.exception("[API ERROR:]")
		sleep(120) 
	except Exception:
		print "Unknown error, check log file"
		logging.exception('[UNKNOWN ERROR:]')
		sleep(120) 