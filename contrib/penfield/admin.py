from django.contrib import admin
from philo.admin import EntityAdmin
from philo.contrib.penfield.models import BlogEntry, Blog, BlogView, Newsletter, NewsletterArticle, NewsletterIssue, NewsletterView


class TitledAdmin(EntityAdmin):
	prepopulated_fields = {'slug': ('title',)}
	list_display = ('title', 'slug')


class BlogAdmin(TitledAdmin):
	pass


class BlogEntryAdmin(TitledAdmin):
	pass


class BlogViewAdmin(EntityAdmin):
	pass


class NewsletterAdmin(TitledAdmin):
	pass


class NewsletterArticleAdmin(TitledAdmin):
	pass


class NewsletterIssueAdmin(TitledAdmin):
	pass


class NewsletterViewAdmin(EntityAdmin):
	pass


admin.site.register(Blog, BlogAdmin)
admin.site.register(BlogEntry, BlogEntryAdmin)
admin.site.register(BlogView, BlogViewAdmin)
admin.site.register(Newsletter, NewsletterAdmin)
admin.site.register(NewsletterArticle, NewsletterArticleAdmin)
admin.site.register(NewsletterIssue, NewsletterIssueAdmin)
admin.site.register(NewsletterView, NewsletterViewAdmin)