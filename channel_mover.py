import streamlit as st
import re
from collections import namedtuple

scene_file = st.file_uploader("Scene file", type="scn")
if not scene_file:
    st.stop()

class Crossbar:
    """Represents a 1-to-1 mapping between old and new.
    
    Example:
    
    >>> cb = Crossbar(n=4)
    >>> cb.connect(0, 1)
    >>> cb.connect(2, 3)
    >>> cb.get_unmapped_olds()
    [1, 3]
    >>> cb.get_unmapped_news()
    [0, 2]
    >>> cb.old_to_new
    [1, None, 3, None]
    >>> cb.new_to_old
    [None, 0, None, 2]
    >>> cb.disconnect(0, 1)
    >>> cb.old_to_new
    [None, None, 3, None]
    >>> cb.new_to_old
    [None, None, None, 2]
    >>> cb.get_unmapped_olds()
    [0, 1, 3]
    >>> cb.get_mappings()
    [(2, 3)]
    """

    def __init__(self, n):
        self.old_to_new = [None] * n
        self.new_to_old = [None] * n

    def connect(self, old, new):
        self.old_to_new[old] = new
        self.new_to_old[new] = old

    def disconnect(self, old, new):
        self.old_to_new[old] = None
        self.new_to_old[new] = None

    def get_mappings(self):
        return [(i, v) for i, v in enumerate(self.old_to_new) if v is not None]
    
    def get_unmapped_olds(self):
        return [i for i, v in enumerate(self.old_to_new) if v is None]
    
    def get_unmapped_news(self):
        return [i for i, v in enumerate(self.new_to_old) if v is None]
    
    def __str__(self):
        return f"Crossbar(old_to_new={self.old_to_new}, new_to_old={self.new_to_old})"
    
    def __repr__(self):
        return str(self)
    
    def __len__(self):
        return len(self.old_to_new)

# run those doctests
import doctest
doctest.testmod()


class ConfigLine(namedtuple("ConfigLine", 'path value')):
    def match_context(self, path):
        return self.path.startswith(path)
    
    def match_setting(self, path):
        return self.path.endswith(path)
    
    @property
    def path_parts(self):
        return self.path.split("/")[1:]
    
    def __str__(self) -> str:
        return f"{self.path} {self.value}"
    
    def with_replaced_path_part(self, index: int, new_value: str) -> "ConfigLine":
        path_parts = self.path_parts.copy()
        path_parts[index] = new_value
        return ConfigLine("/".join(path_parts), self.value)


def parse_cfgline(line):
    """Parse config lines into parts and values.
    Example:
    
    /ch/01/config xxxxx xxxx

    becomes
    
    # ConfigLine(path=['ch', '01', 'config'], value='xxxxx xxxx'])
    ConfigLine(path="/ch/01/config", value="xxxxx xxxx")
    """
    parts = line.split(" ", 1)
    path = parts[0]#.split("/")[1:]
    value = parts[1]
    return ConfigLine(path, value)

# Match channel number and name
# e.g.,
# /ch/01/config "Acoustic Gtr" 23 RD 1
# should match 01 and "Acoustic Gtr"
channel_pattern = re.compile(r"/ch/(\d+)/config\s+\"(.+)\"")

channel_names = {}
lines = scene_file.read().decode('utf-8').splitlines()
# The file starts with a header line
# example:
# #4.0# "Choir" "" %000000000 1    
header = lines.pop(0)
parsed_lines = [parse_cfgline(line) for line in lines]
for line in lines:
    if match := channel_pattern.match(line):
        channel_number = match.group(1)
        channel_name = match.group(2)
        channel_names[f"ch{channel_number}"] = channel_name

for i in range(32):
    num = str(i+1).zfill(2)
    channel_names[f"ch{num}"] = channel_names.get(f"ch{num}", f"Ch {num}")

# The channel crossbar maps old to new channels.
if st.session_state.get('channel_crossbar') is None or st.button("Reset channels"):
    st.session_state.channel_crossbar = Crossbar(n=32)
channel_crossbar = st.session_state.channel_crossbar

st.write(channel_crossbar.get_mappings())

st.header("New Channels")

print("Rerunning")

def handle_change(key, prev_old, prev_new):
    cur_old_channel = st.session_state[key]
    print("Callback", key, cur_old_channel)
    if prev_old is not None:
        channel_crossbar.disconnect(old=prev_old, new=prev_new)
    if cur_old_channel is not None:
        print("connecting", cur_old_channel, prev_new)
        channel_crossbar.connect(old=cur_old_channel, new=prev_new)

for i in range(2):
    num = str(i+1).zfill(2)
    key = f"ch{num}"

    available_channels = channel_crossbar.get_unmapped_olds()
    already_mapped_old_channel_num = channel_crossbar.new_to_old[i]
    options = [None] + available_channels
    index = options.index(already_mapped_old_channel_num)
    
    def format_func(x):
        if x is None:
            return ''
        else:
            return str(x) + channel_names[f"ch{x+1:02d}"]

    st.selectbox(
        f"Channel {num}", [None] + available_channels,
        key=key, index=index,
        format_func=format_func,
        on_change=handle_change,
        kwargs=dict(key=key, prev_old=already_mapped_old_channel_num, prev_new=i))


# Regenerate the scene file
already_warned = {}
new_scene = [header]
for setting in parsed_lines:
    if setting.match_context("/ch"):
        old_channel_num = int(setting.path_parts[1]) - 1
        new_channel_number = channel_crossbar.old_to_new[old_channel_num]
        if new_channel_number is None:
            if not already_warned.get(old_channel_num):
                st.write("Skipping channel ", old_channel_num)
                already_warned[old_channel_num] = True
            continue
        setting = setting.with_replaced_path_part(1, str(new_channel_number + 1).zfill(2))
    
    new_scene.append(str(setting))

st.download_button("Download new scene", "\n".join(new_scene), "scene.scn", mime="text/plain")
st.markdown("```" + "\n".join(new_scene) + "```")