from django import template
from django.conf import settings
from django.utils.safestring import SafeUnicode, mark_safe
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.contenttypes.models import ContentType


register = template.Library()


class ContainerNode(template.Node):
	def __init__(self, name, references=None, as_var=None):
		self.name = name
		self.as_var = as_var
		self.references = references
	def render(self, context):
		content = settings.TEMPLATE_STRING_IF_INVALID
		if 'page' in context:
			page = context['page']
			if self.references:
				try:
					contentreference = page.contentreferences.get(name__exact=self.name, content_type=self.references)
					content = contentreference.content
				except ObjectDoesNotExist:
					pass
			else:
				try:
					contentlet = page.contentlets.get(name__exact=self.name)
					if contentlet.dynamic:
						try:
							content = mark_safe(template.Template(contentlet.content, name=contentlet.name).render(context))
						except template.TemplateSyntaxError, error:
							if settings.DEBUG:
								content = ('[Error parsing contentlet \'%s\': %s]' % self.name, error)
					else:
						content = contentlet.content
				except ObjectDoesNotExist:
					pass
		if content and self.as_var:
			context[self.as_var] = content
			return ''
		return content


def do_container(parser, token):
	"""
	{% container <name> [[references <type>] as <variable>] %}
	"""
	params = token.split_contents()
	if len(params) >= 2:
		name = params[1].strip('"')
		references = None
		as_var = None
		if len(params) > 2:
			remaining_tokens = params[2:]
			while remaining_tokens:
				option_token = remaining_tokens.pop(0)
				if option_token == 'references':
					try:
						app_label, model = remaining_tokens.pop(0).strip('"').split('.')
						references = ContentType.objects.get(app_label=app_label, model=model)
					except IndexError:
						raise template.TemplateSyntaxError('"container" template tag option "references" requires an argument specifying a content type')
					except ValueError:
						raise template.TemplateSyntaxError('"container" template tag option "references" requires an argument of the form app_label.model (see django.contrib.contenttypes)')
					except ObjectDoesNotExist:
						raise template.TemplateSyntaxError('"container" template tag option "references" requires an argument of the form app_label.model which refers to an installed content type (see django.contrib.contenttypes)')
				elif option_token == 'as':
					try:
						as_var = remaining_tokens.pop(0)
					except IndexError:
						raise template.TemplateSyntaxError('"container" template tag option "as" requires an argument specifying a variable name')
			if references and not as_var:
				raise template.TemplateSyntaxError('"container" template tags using "references" option require additional use of the "as" option specifying a variable name')
		return ContainerNode(name, references, as_var)
	else: # error
		raise template.TemplateSyntaxError('"container" template tag provided without arguments (at least one required)')
register.tag('container', do_container)