from rtmbot.core import Plugin
import yaml
import os.path
import jenkins
import re


class BasePlugin(Plugin):

    debug = True  # initial value; will be rewrite from global rtmbot config
    users_ids = {}  # {user_id1:username1, user_id2:username2,}
    user_names = {}  # {username1:user_id1, username2:user_id2,}
    channels = {}  # {channel_id:name,}
    channel_names = {}  # {channelname: channel_id}
    bot_name_dict = {}  # {'user':'B234234', 'username': 'jb'}
    stream_bot_name = ''  # bot name for posting to slak in format: <@botname>
    plugins_count = 0
    # \s+-{0,2}help$  # re for help, -help, --help in the end of string
    help_start = re.compile(r'^[-]{0,2}help\ \s*')
    # in the end: help -help --help -h
    help_end = re.compile(r'\s+[-]{0,2}help$|\s+[-]{1,2}h$')
    # only help, -help, or --help after removing bot name
    help_only = re.compile(r'^[-]{0,2}help$')
    help_middle = re.compile(r'\s+[-]{0,2}help\ \s*')
    help_plugins = re.compile(r'^plugins$')
    help_jenkins = re.compile(r'^jenkins$')

    @classmethod
    def plugins_total(cls):
        return cls.plugins_count

    def __init__(self, name=None, slack_client=None, plugin_config=None):
        super().__init__(name, slack_client, plugin_config)  # init of base class
        BasePlugin.plugins_count += 1
        self.plugin_name = type(self).__name__
        self.cfg = {}  # config from yaml file by path: config/<PluginClassName>.yml
        self.log_channel = 'general'  # default log channel, will be rewrited from rtmbot.conf
        self.work_channels = set()  # set of works channels from plugin config (where jobs can work)
        self.jserver = None

    def print_stdout(self, text):
        """
        Print to stdout without buffering.
        Needed for stdout logs in docker containers.
        The same result with env var PYTHONUNBUFFERED=0
        """
        if BasePlugin.debug:
            # plugin_name = self.get_plugin_name()
            print("{}: {}".format(self.plugin_name, text), flush=True)

    def get_plugin_name(self):
        """
        Get self class name of current plugin.
        Needed for getting plugin config yaml file.
        """
        return type(self).__name__

    def get_bot_name_dict(self):
        """
        Return dict from user_id and username of this rtmbot in Slack.
        """
        if not BasePlugin.bot_name_dict:
            auth_test = self.slack_client.api_call("auth.test")
            if auth_test['ok']:
                BasePlugin.bot_name_dict['user'], BasePlugin.bot_name_dict['username'] = \
                    auth_test['user_id'], auth_test['user']
            else:
                self.print_stdout("auth_test FAILED")
        return BasePlugin.bot_name_dict

    def get_username(self, user):
        """
        Add pairs to users dict: user_id, username.
        Add pairs to user_names dict: username, user_id.
        Return username.
        """
        if user not in BasePlugin.users_ids:
            username = self.slack_client.api_call("users.info", user=user)['user']['name']
            BasePlugin.users_ids[user] = username
            if username not in BasePlugin.user_names:
                BasePlugin.user_names[username] = user
        return BasePlugin.users_ids[user]

    def get_user(self, username):
        """
        Return user id by username from usernames dict.
        """
        if username not in BasePlugin.user_names:
            pass  # TODO: get user_id by username
        return BasePlugin.user_names[username]

    def get_channelname(self, channel):  # TODO: this method needs refactoring
        print("CHANNELS INFO FOR CHANNEL:", channel, self.slack_client.api_call("channels.info", channel=channel))
        if channel not in BasePlugin.channels:
            channelname = ''
            channels_info = self.slack_client.api_call("channels.info", channel=channel)
            if channels_info["ok"]:
                channelname = channels_info['channel']['name']
                BasePlugin.channels[channel] = channelname
            else:
                groups_list = self.slack_client.api_call("groups.list", exclude_archived=True)
                print('GROUPS LIST:', groups_list)
                if groups_list["ok"]:
                    for group in groups_list["groups"]:
                        if group["id"] == channel:
                            channelname = group["name"]
                            BasePlugin.channels[channel] = channelname
            if channel.startswith('D'):
                BasePlugin.channel_names[channelname] = channel
                BasePlugin.channels[channel] = channel
                self.slack_client.api_call("chat.postMessage", channel=channel, text="I'm not working in this channel")

        return BasePlugin.channels[channel]

    def get_channel(self, channelname):
        if channelname not in BasePlugin.channel_names:
            pass  # TODO: get channel id by channel name
        return BasePlugin.channel_names[channelname]

    def get_work_channels(self):
        """
        Works channels from plugin config (where jobs can work)
        """
        for section in self.cfg:
            if 'job' in section:
                for channel in self.cfg[section]["channels"]:
                    self.work_channels.add(channel)
        return ', '.join(self.work_channels)

    def info_message(self, channel, ts, text, user=None):
        if user:
            text = "<@{}> {}".format(user, text)
        self.slack_client.api_call(
            "chat.postMessage",
            channel=channel,
            thread_ts=ts,
            text=text,
            username="Jenkins Deploy Bot",
            icon_emoji=":jenkins-bot:"
        )

    def alert_message(self, channel, ts, text, user=None):
        if user:
            text = "<@{}> {}".format(user, text)
        self.slack_client.api_call(
            "chat.postMessage", channel=channel, thread_ts=ts,
            text=text, username="Jenkins Alert", icon_emoji=":exclamation:"
        )

    # TODO: ts as named param with default value = None (answer into channel)
    def help_message(self, channel, ts, text, user=None):
        if '{@botname}' in text:
            text = text.replace('{@botname}', BasePlugin.stream_bot_name)
        if user:
            text = "<@{}> {}".format(user, text)
        self.slack_client.api_call(
            "chat.postMessage", channel=channel, thread_ts=ts,
            text=text, username="Jenkins Help", icon_emoji=":grey_question:"
        )

    def help_main(self, channel, ts, user):
        channel_permission = False
        output = self.cfg["help"]["answer"]
        for section in self.cfg:
            if 'job' in section and self.check_channel_perm(section, channel):
                channel_permission = True
                trigger = self.cfg[section]["triggers"][0]  # take the first trigger only
                output += "\n`{} {}`".format(BasePlugin.stream_bot_name, trigger)
        if channel_permission:
            self.help_message(channel, ts, output, user=user)
        else:
            output = "No jobs in this channel"
            self.info_message(channel, ts, output, user=user)

    def process_hello(self, data):
        """
        Get from rtmbot.conf log channel name and debug mode.
        Check if Plugin config file exists and load it from yaml.
        Write to logs slack channel starting info.
        """
        with open("config/rtmbot.conf", 'r') as yamlfile:  # not needed to check exists, bot doesn't work without it
            rtmbot_conf = yaml.load(yamlfile)
            if 'LOG_CHANNEL' in rtmbot_conf:
                self.log_channel = rtmbot_conf['LOG_CHANNEL']
            if "DEBUG" in rtmbot_conf:
                self.debug = rtmbot_conf["DEBUG"]

        # self.plugin_name = self.get_plugin_name()
        plugin_conf = "config/" + self.plugin_name + ".yml"
        # bot_name_dict = self.get_bot_name_dict()
        self.print_stdout("bot_name_dict: {}".format(self.get_bot_name_dict()))

        BasePlugin.stream_bot_name = '<@' + BasePlugin.bot_name_dict['user'] + '>'

        if os.path.isfile(plugin_conf):
            with open(plugin_conf, 'r') as ymlfile:
                try:
                    self.cfg = yaml.load(ymlfile)
                    self.print_stdout("Config loaded: {}".format(self.cfg))
                    output = ":white_check_mark: {} config loaded".format(self.plugin_name)
                    self.outputs.append([self.log_channel, output])
                except Exception as e:
                    self.exception_out(e)
        else:
            output = self.plugin_name + " config not loaded (not found)."
            self.print_stdout(output)
            self.outputs.append([self.log_channel, ":warning: " + output])

        output = self.plugin_name + " started"
        output += " (work channels: " + self.get_work_channels() + ")"
        self.print_stdout(output)
        self.outputs.append([self.log_channel, ":white_check_mark: " + output])

        jenkins_conf = "config/jenkins.yml"
        if os.path.isfile(jenkins_conf):
            with open(jenkins_conf, 'r') as jenkins_yml:
                try:
                    jcfg = yaml.load(jenkins_yml)
                    output = self.plugin_name + " Jenkins config loaded"
                    self.print_stdout(output)
                    self.outputs.append([self.log_channel, ":white_check_mark: " + output])

                    # TODO check with try/except
                    self.jserver = jenkins.Jenkins(jcfg['url'], username=jcfg['username'], password=jcfg['password'])
                    jserver_mode = self.jserver.get_info()['mode']
                    output = self.plugin_name + " Jenkins mode: " + jserver_mode
                    self.print_stdout(output)
                    self.outputs.append([self.log_channel, ":white_check_mark: " + output])

                except Exception as e:
                    self.exception_out(e)
        else:
            output = self.plugin_name + " Jenkins config not loaded (not found)"
            self.print_stdout(output)
            self.outputs.append([self.log_channel, ":warning: " + output])

    def exception_out(self, e):
        output = "Exception in " + self.plugin_name + ": " + str(e)
        self.print_stdout(output)
        self.outputs.append([self.log_channel, ":exclamation:" + output + ":exclamation:"])

    def check_channel_perm(self, job, channel):
        channelname = BasePlugin.channels[channel]
        return (channelname in self.cfg[job]["channels"])

    def check_user_perm(self, job, user):
        username = BasePlugin.users_ids[user]
        print(username)
        print(username in self.cfg[job]["users"])
        return (username in self.cfg[job]["users"])

    def build_params_job(self, name, params={'': ''}):
        try:
            self.jserver.build_job(name=name, parameters=params)
        except Exception as e:
            self.exception_out(e)

    def build_job(self, name, user_name=None, channel_name=None):
        """
        Buil Jenkins Job without params in yaml config files (key-value pairs).
        But parameters can be in the Jenkins Job config (for ex., username and slack channel)
        """
        job_has_params = False
        try:
            for prop in self.jserver.get_job_info(name)['property']:
                if 'parameterDefinitions' in prop:
                    job_has_params = True
            if job_has_params:
                if user_name:
                    if channel_name:
                        params = {"USER_NAME": user_name, "CHANNEL_NAME": channel_name}
                    else:
                        params = {"USER_NAME": user_name}
                else:
                    params = {"": ""}
                self.build_params_job(name=name, params=params)
            else:
                self.jserver.build_job(name=name)
        except Exception as e:
            print("Job Has Params:", job_has_params)
            self.exception_out(e)

    def process_message(self, data):
        # plugin_name = self.get_plugin_name()
        if all(key in data for key in ('user', 'text', 'channel', 'ts')):
            channel = data['channel']
            channel_name = self.get_channelname(channel)  # needed to run this method to collect names in dict
            text = str(data['text'])
            user = data['user']
            username = self.get_username(user)  # needed to run this method to collect names in dict
            ts = data['ts']
            if 'thread_ts' in data:
                ts = data['thread_ts']  # if thread stay in thread

            if text.startswith(BasePlugin.stream_bot_name):  # if message like: <@botname> blabla
                string = text.replace(BasePlugin.stream_bot_name, '').strip()  # remove bot name from string
                # if only '<@botname>' or '<@botname> help' or '<@botname> blabla help blabla'
                if not string or BasePlugin.help_only.search(string) or BasePlugin.help_middle.search(string):
                    self.help_main(channel, ts, user)

                elif BasePlugin.help_start.search(string) or BasePlugin.help_end.search(string):
                    if BasePlugin.help_start.search(string):
                        for item in BasePlugin.help_start.split(string):
                            if item:
                                rest = item
                    elif BasePlugin.help_end.search(string):
                        for item in BasePlugin.help_end.split(string):
                            if item:
                                rest = item
                    for section in self.cfg:
                        if 'job' in section:
                            for trigger in self.cfg[section]["triggers"]:
                                if trigger == rest:
                                    if 'help' in self.cfg[section] and 'answer' in self.cfg[section]["help"]:
                                        output = '\n' + self.cfg[section]["help"]["answer"]
                                        if "parameters" in self.cfg[section]:
                                            for parameter in self.cfg[section]["parameters"]:
                                                if self.cfg[section]["parameters"][parameter]:
                                                    output += '`'
                                                    for item in self.cfg[section]["parameters"][parameter]:
                                                        output += item + ', '
                                                    output += '`\n'
                                        self.help_message(channel, ts, output, user=user)

                elif BasePlugin.help_plugins.search(string):
                    output = "Number of plugins: " + str(BasePlugin.plugins_total())
                    output += "\nHello from " + self.plugin_name
                    self.help_message(channel, ts, output)
                    # self.help_message(channel, ts, "Hello from " + self.plugin_name)

                elif BasePlugin.help_jenkins.search(string):
                    output = "Plugin: {}. Jenkins mode: {}".format(self.plugin_name, self.jserver.get_info()['mode'])
                    self.help_message(channel, ts, output)

                else:  # Run jenkins jobs if triggers
                    trigger_found = False
                    for section in self.cfg:
                        if 'job' in section:
                            for trigger in self.cfg[section]["triggers"]:
                                if trigger in string and self.check_channel_perm(section, channel):
                                    trigger_found = True
                                    if self.check_user_perm(section, user):
                                        if "parameters" in self.cfg[section]:
                                            cmd_words = string.replace(trigger, '').split()
                                            dict_params = {}
                                            for i in range(0, len(cmd_words), 2):
                                                for parameter in self.cfg[section]["parameters"]:
                                                    if cmd_words[i] in self.cfg[section]["parameters"][parameter]:
                                                        if i + 1 < len(cmd_words):
                                                            dict_params[parameter] = cmd_words[i + 1]
                                            if dict_params:  # message with jenkins icon: try to run job with params:
                                                output = "Trying to start job with parameters:\n{}".format(dict_params)
                                                self.info_message(channel, ts, output, user=user)
                                                self.build_params_job(self.cfg[section]["name"], params=dict_params)
                                                # TODO: if params in job and not dict_params - output part of help
                                            else:
                                                output = "Job needs right parameters"
                                                self.alert_message(channel, ts, output, user=user)
                                            # if no params in job => run job without params
                                        elif trigger == string:  # trigger without params in command
                                            # Run job without params
                                            output = "Trying to start job: {}".format(self.cfg[section]["name"])
                                            self.info_message(channel, ts, output, user=user)
                                            # TODO: check job existance
                                            self.build_job(
                                                self.cfg[section]["name"],
                                                user_name=username,
                                                channel_name=channel_name)
                                        else:
                                            pass  # TODO: does it needed to do something here?
                                    else:
                                        output = "Running this job is not allowed for user"
                                        self.alert_message(channel, ts, output, user=user)

                    if not trigger_found:
                        output = "I'm sorry, I don't understand your command. Try to type '@" + \
                            BasePlugin.bot_name_dict['username'] + " help'"
                        self.alert_message(channel, ts, output, user=user)
