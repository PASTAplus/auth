-- Migration 001

-- identity

CREATE TABLE identity_new (
  id INTEGER NOT NULL,
  profile_id INTEGER NOT NULL,
  idp_name VARCHAR NOT NULL,
  idp_uid VARCHAR NOT NULL,
  email VARCHAR,
  first_auth DATETIME NOT NULL,
  last_auth DATETIME NOT NULL,
  has_avatar BOOLEAN NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT idp_name_uid_unique UNIQUE (idp_name, idp_uid),
  CONSTRAINT idp_name_check CHECK (idp_name IN ('github', 'google', 'ldap', 'microsoft', 'orcid')),
  FOREIGN KEY(profile_id) REFERENCES profile (id)
);

insert into identity_new (
  id,
  profile_id,
  idp_name,
  idp_uid,
  email,
  first_auth,
  last_auth,
  has_avatar
)
select
  id,
  profile_id,
  idp_name,
  idp_uid,
  email,
  first_auth,
  last_auth,
  false
from identity
;

drop table identity;
alter table identity_new rename to identity;

-- profile

CREATE TABLE profile_new (
	id INTEGER NOT NULL,
	pasta_id VARCHAR NOT NULL,
	given_name VARCHAR,
	family_name VARCHAR,
	email VARCHAR,
	email_notifications BOOLEAN NOT NULL,
	privacy_policy_accepted BOOLEAN NOT NULL,
	privacy_policy_accepted_date DATETIME,
	organization VARCHAR,
	association VARCHAR,
	has_avatar BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (pasta_id)
);

insert into profile_new (
	id,
	pasta_id,
	given_name,
	family_name,
	email,
	email_notifications,
	privacy_policy_accepted,
	privacy_policy_accepted_date,
	organization,
	association,
	has_avatar
)
select
  id,
  pasta_id,
  given_name,
  family_name,
  email,
  false,
  privacy_policy_accepted,
  privacy_policy_accepted_date,
  '',
  '',
  false
from profile
;

drop table profile;
alter table profile_new rename to profile;
