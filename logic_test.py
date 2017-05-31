import os.path
import random

import pytest
import mock

import logic as l

l._S_OLD = l._SENDGRID
l._SENDGRID = mock.Mock()


@pytest.fixture(autouse=True)
def transact():
    """Since the whole point of bcrypt is to be slow, it helps to dial the knob
        down while testing."""
    l._SALT_ROUNDS=4
    e = l._e
    q = "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    for table in e.execute(q).fetchall():
        table = table[0]
        e.execute('DROP TABLE IF EXISTS %s CASCADE' % table)
    sql = open(os.path.join(os.path.dirname(__file__), 'tables.sql')).read()
    e.execute(sql)   

def test_pw():
    pw = ['blah blah blah', 'blah blah blah',
            "\u2603", 'Blah Blah Blah']
    for p in pw:
        s = l._mangle_pw(p)
        assert s
        assert s == l._mangle_pw(p, s)

def test_user_basics():
    for n in range(20):
        assert l.add_user('{}@example.com'.format(n), 'Name {}'.format(n),
                            'pw{}'.format(n))


    email = 'ned@example.com'
    name = 'Ned Jackson Lovely'
    pw = 'password'

    assert not l.check_pw(email, pw)

    uid = l.add_user(email, name, pw)
    
    assert len(l.list_users()) == 21

    for user in l.list_users():
        assert not user.approved_on 

    l.approve_user(uid)

    for user in l.list_users():
        assert not user.approved_on if user.id != uid else user.approved_on


    assert l.get_user(uid).display_name == name

    assert l.check_pw(email, pw)
    assert l.check_pw(email.upper(), pw)
    assert not l.check_pw(email, pw.upper())

    pw2 = '\u2603'
    l.change_pw(uid, pw2)

    assert not l.check_pw(email, pw)
    assert l.check_pw(email, pw2)


data = {'id': 123, 'title': 'Title Here', 'category': 'Python',
        'duration': '30', 'description':'the description goes here.',
        'audience': 'People who want to learn about python',
        'audience_level': 'Intermediate', 'objective': 'Talk about Python',
        'abstract':'This is an abstract\n#This is a headline\nThis is not.', 
        'outline':"First I'll talk about one thing, then another",
        'notes': 'Additional stuff', 'recording_release': True,
        'additional_requirements':'I need a fishtank',
        'authors': [{'name':'Person Personson','email':'person@example.com'}]}

def test_proposal_basics():
    assert l.add_proposal(data)
    assert not l.add_proposal(data)
    assert l.get_proposal(data['id']).data['outline'] == data['outline']

    changed = data.copy()
    changed['abstract'] = 'This is a longer abstract.'

    assert l.add_proposal(changed)

def test_voting_basics():
    l.add_proposal(data)
    standards = [l.add_standard("About Pythong"), l.add_standard("Awesome")]
    uid = l.add_user('bob@example.com', 'Bob', 'bob')
    assert not l.get_votes(123)
    assert not l.vote(uid, 123, {k:3 for k in standards})
    assert not l.get_votes(123)

    assert l.get_proposal(123).vote_count == 0

    l.approve_user(uid)

    assert not l.vote(uid, 123, {})
    assert not l.get_votes(123)

    assert l.vote(uid, 123, {k:2 for k in standards})
    assert l.get_votes(123)[0].scores == {k:2 for k in standards}
    assert l.get_proposal(123).vote_count == 1

    assert not l.vote(uid, 123, {k:7 for k in standards})
    assert l.get_votes(123)[0].scores == {k:2 for k in standards}

    assert l.vote(uid, 123, {k:0 for k in standards})
    assert len(l.get_votes(123)) == 1
    assert l.get_votes(123)[0].scores == {k:0 for k in standards}
    assert l.get_proposal(123).vote_count == 1


def test_needs_votes():
    proposals = []
    users = {}
    standards = [l.add_standard("About Pythong"), l.add_standard("Awesome")]
    sample_vote = {k:2 for k in standards}
    for n in range(1,10):
        prop = data.copy()
        prop['id'] = n*2
        prop['abstract'] = 'Proposal {}'.format(n)
        email = '{}@example.com'.format(n)
        uid = l.add_user(email, email, email)
        l.approve_user(uid)
        users[email] = uid
        prop['authors'] = [{'email':email, 'name':'foo'}]
        l.add_proposal(prop)
        proposals.append(n*2)

    non_author_email = 'none@example.com'
    non_author_id = l.add_user(non_author_email, non_author_email, non_author_email)
    l.approve_user(non_author_id)

    random.seed(0)
    seen_ids = set()
    for n in range(100):
        seen_ids.add(l.needs_votes(non_author_email, non_author_id))
    assert seen_ids == set(proposals)

    seen_ids = set()
    for n in range(100):
        seen_ids.add(l.needs_votes('2@example.com', users['2@example.com']))
    not_2_proposals = set(proposals)
    not_2_proposals.remove(4)
    assert seen_ids == not_2_proposals

    for n in range(1, 9):
        l.vote(users['8@example.com'], n*2, sample_vote)

    seen_ids = set()
    for n in range(100):
        seen_ids.add(l.needs_votes(non_author_email, non_author_id))
    assert seen_ids == set([18])

    l.vote(users['8@example.com'], 18, sample_vote)

    seen_ids = set()
    for n in range(100):
        seen_ids.add(l.needs_votes(non_author_email, non_author_id))
    assert seen_ids == set(proposals)

def test_standards():
    assert l.get_standards() == []
    l.add_standard('Bob')
    assert l.get_standards()[0].description == 'Bob'


def test_discussion():
    l.add_proposal(data)
    proposal = data['id']

    users = []
    for n in range(10):
        uid = l.add_user('{}@example.com'.format(n), 'name {}'.format(n), 'blah')
        l.approve_user(uid)
        users.append(uid)

    l.add_to_discussion(users[0], proposal, 'Lorem ipsum')

    for u in users:
        assert len(l.get_unread(u)) == 0

    assert len(l.get_discussion(proposal)) == 1
    assert l.get_discussion(proposal)[0].body == 'Lorem ipsum'

    l.add_to_discussion(users[-1], proposal, 'dolor sit')
    assert [x.id for x in l.get_unread(users[0])] == [proposal]
    l.add_to_discussion(users[-1], proposal, 'amet, consectetur')
    assert [x.id for x in l.get_unread(users[0])] == [proposal]

    l.mark_read(users[0], proposal)
    for u in users:
        assert len(l.get_unread(u)) == 0

    l.add_to_discussion(users[0], proposal, 'LOREM IPSUM')
    assert l.get_discussion(proposal)[-1].body == 'LOREM IPSUM'
    assert l.get_discussion(proposal)[0].body == 'Lorem ipsum'

def test_batch():

    user = l.add_user('example@example.com', 'Voter', '123')
    l.approve_user(user)

    submitter = l.add_user('bob@example.com', 'Submitted', '123')
    l.approve_user(submitter)

    proposals = []
    for n in range(1,50):
        prop = data.copy()
        prop['id'] = n
        if n == 6:
            prop['authors'] = [{'name':'Blah', 'email':'bob@example.com'}]
        proposals.append(l.add_proposal(prop))

    group_one = l.create_group('Group One', proposals[4:10])
    group_two = l.create_group('Group Two', proposals[16:27])

    assert l.get_group(group_one).name == 'Group One'

    group_one_proposals = l.get_group_proposals(group_one)
    assert set(x.id for x in group_one_proposals) == set(proposals[4:10])
   
    all_groups = l.list_groups(user)
    assert set([group_one, group_two]) == set(x.id for x in all_groups)
    assert not any(x.voted for x in all_groups)

    votes1 = list(reversed(proposals[5:6]))
    votes2 = proposals[4:5]

    l.vote_group(group_one, user, votes1)

    all_groups = {x.id:x.voted for x in l.list_groups(user)}
    assert all_groups[group_one]
    assert not all_groups[group_two]

    assert l.get_batch_vote(group_one, user).accept == votes1

    l.vote_group(group_one, user, votes2)

    assert l.get_batch_vote(group_one, user).accept == votes2

    assert len(l.list_groups(submitter)) == 1
