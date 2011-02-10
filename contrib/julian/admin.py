from django.contrib import admin
from philo.admin import EntityAdmin
from philo.contrib.julian.models import Location, Event, Calendar


class LocationAdmin(EntityAdmin):
	pass


class EventAdmin(EntityAdmin):
	fieldsets = (
		(None, {
			'fields': ('title', 'description', 'tags', 'parent_event', 'owner')
		}),
		('Location', {
			'fields': ('location_content_type', 'location_pk')
		}),
		('Time', {
			'fields': (('start_date', 'start_time'), ('end_date', 'end_time'),),
		})
	)
	related_lookup_fields = {
		'generic': [["location_content_type", "location_pk"]]
	}


class CalendarAdmin(EntityAdmin):
	pass


admin.site.register(Location, LocationAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Calendar, CalendarAdmin)