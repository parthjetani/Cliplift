"""Publisher abstraction — pushes scheduled posts to platforms.

Mirror of `app.platforms` but for *writing* to platforms instead of *reading*.
The QStash publish-scheduled worker pulls a `PublisherRouter` off `app.state`
and dispatches each due post to the right concrete publisher.
"""
