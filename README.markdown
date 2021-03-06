Philo is a foundation for developing web content management systems.

Prerequisites:

 * [Python 2.5.4+ &lt;http://www.python.org&gt;](http://www.python.org/)
 * [Django 1.3+ &lt;http://www.djangoproject.com/&gt;](http://www.djangoproject.com/)
 * [django-mptt e734079+ &lt;https://github.com/django-mptt/django-mptt/&gt;](https://github.com/django-mptt/django-mptt/)
 * (Optional) [django-grappelli 2.0+ &lt;http://code.google.com/p/django-grappelli/&gt;](http://code.google.com/p/django-grappelli/)
 * (Optional) [south 0.7.2+ &lt;http://south.aeracode.org/)](http://south.aeracode.org/)
 * (Optional) [recaptcha-django r6 &lt;http://code.google.com/p/recaptcha-django/&gt;](http://code.google.com/p/recaptcha-django/)

To contribute, please visit the [project website](http://project.philocms.org/) and/or make a fork of the git repository on [GitHub](http://github.com/ithinksw/philo) or [Gitorious](http://gitorious
.org/ithinksw/philo). Feel free to join us on IRC at [irc://irc.oftc.net/#philo](irc://irc.oftc.net/#philo).

Using philo
===========

After installing philo and mptt on your python path, make sure to complete the following steps:

1. add 'philo.middleware.RequestNodeMiddleware' to settings.MIDDLEWARE_CLASSES.
2. add 'philo' and 'mptt' to settings.INSTALLED_APPS.
3. include 'philo.urls' somewhere in your urls.py file.
4. Optionally add a root node to your current Site.

Philo should be ready to go!
