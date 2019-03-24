Installation
============
Bitcart is a platform for merchants, users and developers which offers easy setup and use.


Automatic
*********
Now we offer docker automatic installation!

https://github.com/MrNaif2018/bitcart-docker

https://hub.docker.com/r/mrnaif/bitcart

Manual
******
Manual installation requires setting up essential parts of bitcart structure.
First of all, you will need to download bitcart repository:

.. code-block:: sh

    git clone https://github.com/MrNaif2018/bitcart

Then, install all the requirements. Note that using virtualenv is preferred, but not required.

Create virtualenv(with name env):

.. code-block:: sh

    virtualenv env

Then, activate it, it may differ on your os, but on most oses it would be:

.. code-block:: sh

    source env/bin/activate

Then, install the requirements:

.. code-block:: sh

    pip install -r requirements.txt

After that, you will need to set up bitcart structure,
it consists of:
a database(postgresql), in-memory cache provider(memcached), in-memory message queue(rabbitmq), celery worker
and blockchain access provider(electrum daemon).
So, you will need to install those and make it running, default settings are set up to work with default
installations of these pieces of software.
After installing memcached, rabbitmq and postgres, you will need to create postgres datatabase.
Default settings are configured to use user postgres with database bitcart
Login to postgres using something like:

.. code-block:: sh

    sudo -u postgres psql
    \password your-password-here
    CREATE DATABASE bitcart OWNER postgres;
    \q

This will set password for your user postgres as your-password-here(you will need to use your password),
and create database named bitcart with user postgres as owner.

Now, you will need to create a config file. For that, we provided a .env.sample file
in conf directory, adjust it to your needs(for example DB_PASSWORD to your-password-here).

After that, it is time to run bitcart. It will need a celery worker and daemon to be running.
Open terminal and type:

.. code-block:: sh

    celery worker -A mainsite

To run celery worker, and in separate
terminal, run:

.. code-block:: sh

    python3 daemon.py

To run electrum daemon.

Bitcart web gui is a django site, so you will need to create database tables first, run:

.. code-block:: sh

    python3 manage.py makemigrations --no-input
    python3 manage.py makemigrations gui --no-input
    python3 manage.py migrate --no-input

Next, if you need to create admin user(to access django control panel at /admin),
run:

.. code-block:: sh

    python3 manage.py createsuperuser

It will ask you for admin user's username,email and password.

Now, we're ready!
Run bitcart using this command in separate terminal:

.. code-block:: sh

    python3 manage.py runserver

Now, you can open your browser at http://localhost:8000 and see your bitcart instance up and running!