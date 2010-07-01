from django.db import models
from django.conf import settings
from philo.models import Tag, Titled, Entity, MultiView, Page, register_value_model
from django.conf.urls.defaults import url, patterns
from django.http import Http404, HttpResponse
from datetime import datetime


class Blog(Entity, Titled):
	@property
	def entry_tags(self):
		""" Returns a QuerySet of Tags that are used on any entries in this blog. """
		return Tag.objects.filter(blogentries__blog=self)


class BlogEntry(Entity, Titled):
	blog = models.ForeignKey(Blog, related_name='entries')
	author = models.ForeignKey(getattr(settings, 'PHILO_PERSON_MODULE', 'auth.User'), related_name='blogentries')
	date = models.DateTimeField(default=datetime.now)
	content = models.TextField()
	excerpt = models.TextField()
	tags = models.ManyToManyField(Tag, related_name='blogentries')
	
	class Meta:
		ordering = ['-date']
		verbose_name_plural = "blog entries"


register_value_model(BlogEntry)


class BlogView(MultiView):
	ENTRY_PERMALINK_STYLE_CHOICES = (
		('D', 'Year, month, and day'),
		('M', 'Year and month'),
		('Y', 'Year'),
		('B', 'Custom base'),
		('N', 'No base')
	)
	
	blog = models.ForeignKey(Blog, related_name='blogviews')
	
	index_page = models.ForeignKey(Page, related_name='blog_index_related')
	entry_page = models.ForeignKey(Page, related_name='blog_entry_related')
	entry_archive_page = models.ForeignKey(Page, related_name='blog_entry_archive_related', null=True, blank=True)
	tag_page = models.ForeignKey(Page, related_name='blog_tag_related')
	tag_archive_page = models.ForeignKey(Page, related_name='blog_tag_archive_related', null=True, blank=True)
	
	entry_permalink_style = models.CharField(max_length=1, choices=ENTRY_PERMALINK_STYLE_CHOICES)
	entry_permalink_base = models.CharField(max_length=255, blank=False, default='entries')
	tag_permalink_base = models.CharField(max_length=255, blank=False, default='tags')
	
	@property
	def urlpatterns(self):
		base_patterns = patterns('',
			url(r'^$', self.index_view),
			url((r'^(?:%s)/?$' % self.tag_permalink_base), self.tag_archive_view),
			url((r'^(?:%s)/(?P<tag>[-\w]+)/?$' % self.tag_permalink_base), self.tag_view)
		)
		if self.entry_permalink_style == 'D':
			entry_patterns = patterns('',
				url(r'^(?P<year>\d{4})/?$', self.entry_archive_view),
				url(r'^(?P<year>\d{4})/(?P<month>\d{2})/?$', self.entry_archive_view),
				url(r'^(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/?$', self.entry_archive_view),
				url(r'^(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/(?P<slug>[-\w]+)/?$', self.entry_view)
			)
		elif self.entry_permalink_style == 'M':
			entry_patterns = patterns('',
				url(r'^(?P<year>\d{4})/?$', self.entry_archive_view),
				url(r'^(?P<year>\d{4})/(?P<month>\d{2})/?$', self.entry_archive_view),
				url(r'^(?P<year>\d{4})/(?P<month>\d{2})/(?P<slug>[-\w]+)/?$', self.entry_view)
			)
		elif self.entry_permalink_style == 'Y':
			entry_patterns = patterns('',
				url(r'^(?P<year>\d{4})/?$', self.entry_archive_view),
				url(r'^(?P<year>\d{4})/(?P<slug>[-\w]+)/?$', self.entry_view)
			)
		elif self.entry_permalink_style == 'B':
			entry_patterns = patterns('',
				url((r'^(?:%s)/?$' % self.entry_permalink_base), self.entry_archive_view),
				url((r'^(?:%s)/(?P<slug>[-\w]+)/?$' % self.entry_permalink_base), self.entry_view)
			)
		else:
			entry_patterns = patterns('',
				url(r'^(?P<slug>[-\w]+)/?$', self.entry_view)
			)
		return base_patterns + entry_patterns
	
	def index_view(self, request, node=None, extra_context=None):
		context = {}
		context.update(extra_context or {})
		context.update({'blog': self.blog})
		return self.index_page.render_to_response(node, request, extra_context=context)
	
	def entry_view(self, request, slug, year=None, month=None, day=None, node=None, extra_context=None):
		entries = self.blog.entries.all()
		if year:
			entries = entries.filter(date__year=year)
		if month:
			entries = entries.filter(date__month=month)
		if day:
			entries = entries.filter(date__day=day)
		try:
			entry = entries.get(slug=slug)
		except:
			raise Http404
		context = {}
		context.update(extra_context or {})
		context.update({'blog': self.blog, 'entry': entry})
		return self.entry_page.render_to_response(node, request, extra_context=context)
	
	def entry_archive_view(self, request, year=None, month=None, day=None, node=None, extra_context=None):
		if not self.entry_archive_page:
			raise Http404
		entries = self.blog.entries.all()
		if year:
			entries = entries.filter(date__year=year)
		if month:
			entries = entries.filter(date__month=month)
		if day:
			entries = entries.filter(date__day=day)
		context = {}
		context.update(extra_context or {})
		context.update({'blog': self.blog, 'year': year, 'month': month, 'day': day, 'entries': entries})
		return self.entry_archive_page.render_to_response(node, request, extra_context=context)
	
	def tag_view(self, request, tag, node=None, extra_context=None):
		try:
			tag = self.blog.entry_tags.filter(slug=tag)
		except:
			raise Http404
		entries = self.blog.entries.filter(tags=tag)
		context = {}
		context.update(extra_context or {})
		context.update({'blog': self.blog, 'tag': tag, 'entries': entries})
		return self.tag_page.render_to_response(node, request, extra_context=context)
	
	def tag_archive_view(self, request, node=None, extra_context=None):
		if not self.tag_archive_page:
			raise Http404
		context = {}
		context.update(extra_context or {})
		context.update({'blog': self.blog})
		return self.tag_archive_page.render_to_response(node, request, extra_context=context)


class Newsletter(Entity, Titled):
	pass


class NewsletterArticle(Entity, Titled):
	newsletter = models.ForeignKey(Newsletter, related_name='articles')
	authors = models.ManyToManyField(getattr(settings, 'PHILO_PERSON_MODULE', 'auth.User'), related_name='newsletterarticles')
	date = models.DateTimeField(default=datetime.now)
	lede = models.TextField(null=True, blank=True)
	full_text = models.TextField()
	
	class Meta:
		ordering = ['-date']
		unique_together = (('newsletter', 'slug'),)


register_value_model(NewsletterArticle)


class NewsletterIssue(Entity, Titled):
	newsletter = models.ForeignKey(Newsletter, related_name='issues')
	number = models.PositiveIntegerField()
	articles = models.ManyToManyField(NewsletterArticle)
	
	class Meta:
		ordering = ['-number']
		unique_together = (('newsletter', 'number'),)


class NewsletterView(MultiView):
	ARTICLE_PERMALINK_STYLE_CHOICES = (
		('D', 'Year, month, and day'),
		('M', 'Year and month'),
		('Y', 'Year'),
		('S', 'Slug only')
	)
	
	newsletter = models.ForeignKey(Newsletter, related_name='newsletterviews')
	
	index_page = models.ForeignKey(Page, related_name='newsletter_index_related')
	article_page = models.ForeignKey(Page, related_name='newsletter_article_related')
	article_archive_page = models.ForeignKey(Page, related_name='newsletter_article_archive_related', null=True, blank=True)
	issue_page = models.ForeignKey(Page, related_name='newsletter_issue_related')
	issue_archive_page = models.ForeignKey(Page, related_name='newsletter_issue_archive_related', null=True, blank=True)
	
	article_permalink_style = models.CharField(max_length=1, choices=ARTICLE_PERMALINK_STYLE_CHOICES)
	article_permalink_base = models.CharField(max_length=255, blank=False, default='articles')
	issue_permalink_base = models.CharField(max_length=255, blank=False, default='issues')
	
	@property
	def urlpatterns(self):
		base_patterns = patterns('',
			url(r'^$', self.index_view),
			url((r'^(?:%s)/?$' % self.issue_permalink_base), self.issue_archive_view),
			url((r'^(?:%s)/(?P<number>\d+)/?$' % self.issue_permalink_base), self.issue_view)
		)
		article_patterns = patterns('',
			url((r'^(?:%s)/?$' % self.article_permalink_base), self.article_archive_view)
		)
		if self.article_permalink_style in 'DMY':
			article_patterns += patterns('',
				url((r'^(?:%s)/(?P<year>\d{4})/?$' % self.article_permalink_base), self.article_archive_view)
			)
			if self.article_permalink_style in 'DM':
				article_patterns += patterns('',
					url((r'^(?:%s)/(?P<year>\d{4})/(?P<month>\d{2})/?$' % self.article_permalink_base), self.article_archive_view)
				)
				if self.article_permalink_style == 'D':
					article_patterns += patterns('',
						url((r'^(?:%s)/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/?$' % self.article_permalink_base), self.article_archive_view),
						url((r'^(?:%s)/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/(?P<slug>[-\w]+)/?$' % self.article_permalink_base), self.article_view)
					)
				else:
					article_patterns += patterns('',
						url((r'^(?:%s)/(?P<year>\d{4})/(?P<month>\d{2})/(?P<slug>[-\w]+)/?$' % self.article_permalink_base), self.article_view)
					)
			else:
				article_patterns += patterns('',
					url((r'^(?:%s)/(?P<year>\d{4})/(?P<slug>[-\w]+)/?$' % self.article_permalink_base), self.article_view)
				)
		else:
			article_patterns += patterns('',
				url((r'^(?:%s)/(?P<slug>[-\w]+)/?$' % self.article_permalink_base), self.article_view)
			)
		return base_patterns + article_patterns
	
	def index_view(self, request, node=None, extra_context=None):
		context = {}
		context.update(extra_context or {})
		context.update({'newsletter': self.newsletter})
		return self.index_page.render_to_response(node, request, extra_context=context)
	
	def article_view(self, request, slug, year=None, month=None, day=None, node=None, extra_context=None):
		articles = self.newsletter.articles.all()
		if year:
			articles = articles.filter(date__year=year)
		if month:
			articles = articles.filter(date__month=month)
		if day:
			articles = articles.filter(date__day=day)
		try:
			article = articles.get(slug=slug)
		except:
			raise Http404
		context = {}
		context.update(extra_context or {})
		context.update({'newsletter': self.newsletter, 'article': article})
		return self.article_page.render_to_response(node, request, extra_context=context)
	
	def article_archive_view(self, request, year=None, month=None, day=None, node=None, extra_context=None):
		if not self.article_archive_page:
			raise Http404
		articles = self.newsletter.articles.all()
		if year:
			articles = articles.filter(date__year=year)
		if month:
			articles = articles.filter(date__month=month)
		if day:
			articles = articles.filter(date__day=day)
		context = {}
		context.update(extra_context or {})
		context.update({'newsletter': self.newsletter, 'year': year, 'month': month, 'day': day, 'articles': articles})
		return self.article_archive_page.render_to_response(node, request, extra_context=context)
	
	def issue_view(self, request, number, node=None, extra_context=None):
		try:
			issue = self.newsletter.issues.get(number=number)
		except:
			raise Http404
		context = {}
		context.update(extra_context or {})
		context.update({'newsletter': self.newsletter, 'issue': issue})
		return self.issue_page.render_to_response(node, request, extra_context=context)
	
	def issue_archive_view(self, request, node=None, extra_context=None):
		if not self.issue_archive_page:
			raise Http404
		context = {}
		context.update(extra_context or {})
		context.update({'newsletter': self.newsletter})
		return self.issue_archive_page.render_to_response(node, request, extra_context=context)