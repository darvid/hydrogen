hydrogen
========

Python web development in the era of Javascript is awkward. [Bower] makes
life easy for frontend applications, but what if you want to bundle your
frontend with a Python package? What if you want to be able to manage
client-side dependencies without requiring the entire node stack? What
if you could install Python packages like this, without man-handling
your requirements file?

    pip install flask --save

Now you can.

### Examples

```shell
# Install Flask as a Python package, save to requirements.yml
$ hydrogen install flask --save
# Install IPython as a Python package as a development dependency
$ hydrogen install ipython --save-dev
# Install Bootstrap as a bower package
$ hydrogen install bootstrap --bower --save
# Show requirements listed in requirements.yml
$ hydrogen freeze
```


### Credits

This project uses code (currently, only the ``werkzeug.utils.secure_filename``
function) written by the [Werkzeug] team, which is licensed under the [BSD
3-clause license](https://github.com/mitsuhiko/werkzeug/blob/master/LICENSE).

[Bower]: http://bower.io
[Werkzeug]: http://werkzeug.pocoo.org