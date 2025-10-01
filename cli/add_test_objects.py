#!/usr/bin/env python

"""Fill the Profile, Resource, Rule, Group and GroupMember tables with randomized test objects.
- This assumes that the database is empty and was prepared with 'db_manager.py'.
- As we do not insert IdPs, it's not possible to log into the profiles that are created.
- Triggers automatically populate the PackageScope, ResourceType and RootResource search tables as
the resources are created.
"""
import argparse
import asyncio
import logging
import pathlib
import random
import sys
import uuid

import daiquiri
import sqlalchemy.exc

BASE_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((BASE_PATH / 'webapp').as_posix())

import db.db_interface
import db.models.group
import db.models.permission
import db.models.profile
import db.models.search
import db.session
import util.dependency

from config import Config

SYSTEM_PROFILE_EDI_ID_LIST = (
    Config.SERVICE_EDI_ID,
    Config.PUBLIC_EDI_ID,
    Config.AUTHENTICATED_EDI_ID,
)

log = daiquiri.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--debug', help='Debug level logging')
    args = parser.parse_args()

    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

    answer_str = input('Add test objects to the PRODUCTION database? (y/n): ')
    if answer_str.lower() != 'y':
        log.info('Cancelled')
        return 1

    async with util.dependency.get_session() as session:
        dbi = db.db_interface.DbInterface(session)
        # Add user profiles.
        await add_profiles(dbi)
        # Add resources and assign random permissions to them.
        await add_permissions(session)
        # Add groups and group members last, so the permissions created to track the groups do not
        # interfere with the permissions created for the regular resources.
        await add_groups(dbi)

    log.info('Success!')

    return 0


#
# Profiles
#


async def add_profiles(dbi):
    for common_name in RANDOM_PERSON_NAME_LIST:
        given_name, family_name = common_name.split(' ')
        email = f'{given_name.lower()}@{family_name.lower()}.com'
        await dbi.create_profile(
            idp_name=db.models.profile.IdpName.SKELETON,
            idp_uid=None,
            common_name=common_name,
            email=email,
        )
    log.info('Profiles have been added')


#
# Groups
#


async def add_groups(dbi):
    profile_row_list = await get_user_profile_rows(dbi)
    for profile_row in profile_row_list:
        await insert_groups(dbi, profile_row, profile_row_list)
    log.info('Groups and group members have been added')


async def insert_groups(dbi, profile_row, profile_row_list):
    group_count = random.randrange(0, 5)
    for group_idx in range(group_count):
        name = f'{profile_row.common_name}\'s group #{group_idx}'
        group_row, _ = await dbi.create_group(profile_row, name, None)
        await insert_members(dbi, group_row, profile_row_list)


async def insert_members(dbi, group_row, profile_row_list):
    member_count = random.randrange(1, 5)
    sampled_profile_row_list = random.sample(profile_row_list, member_count)
    for profile_row in sampled_profile_row_list:
        new_group_member = db.models.group.GroupMember(
            group=group_row,
            profile=profile_row,
        )
        dbi.session.add(new_group_member)


async def get_user_profile_rows(dbi):
    return (
        (
            await dbi.session.execute(
                sqlalchemy.select(db.models.profile.Profile).where(
                    ~db.models.profile.Profile.edi_id.in_(SYSTEM_PROFILE_EDI_ID_LIST)
                )
            )
        )
        .scalars()
        .all()
    )


#
# Permissions
#


async def add_permissions(session):
    for scope in RANDOM_SCOPE_TUP:
        id_count = random.randrange(1, 100)
        id_ = random.randrange(1, 10000)
        for i in range(id_count):
            id_ += random.randrange(1, 100)
            ver_count = random.randrange(1, 10)
            for ver in range(1, ver_count):
                label = f'{scope}.{id_}.{ver}'
                log.info(label)
                # Package (root resource)
                package_id = await insert_resource(
                    session, None, await get_random_resource_key(), label, 'package'
                )
                # Metadata
                metadata_id = await insert_resource(
                    session, package_id, await get_random_resource_key(), 'Metadata', 'collection'
                )
                await insert_resource(
                    session,
                    metadata_id,
                    await get_random_resource_key(),
                    'quality_report.xml',
                    'metadata',
                )
                await insert_resource(
                    session,
                    metadata_id,
                    await get_random_resource_key(),
                    'metadata.eml',
                    'metadata',
                )
                # Data
                data_id = await insert_resource(
                    session, package_id, await get_random_resource_key(), 'Data', 'collection'
                )
                data_count = random.randrange(1, 10)
                for j in range(data_count):
                    await insert_resource(
                        session,
                        data_id,
                        await get_random_resource_key(),
                        random.choice(RANDOM_FILE_NAME_TUP)
                        + random.choice(('.csv', '.txt', '.jpg', '.tiff')),
                        'data',
                    )

        log.info('')

    principal_row_list = await get_principal_row_list(session)
    resource_row_list = await get_resource_row_list(session)
    await insert_permissions(session, resource_row_list, principal_row_list)

    log.info('Resources and permissions have been added')


async def get_random_resource_key():
    v = list(uuid.uuid4().hex)
    v[5] = '/'
    v[20] = '/'
    return ''.join(v)


async def insert_resource(session, parent_id, resource_key, resource_label, resource_type):
    new_resource = db.models.permission.Resource(
        parent_id=parent_id,
        key=resource_key,
        label=resource_label,
        type=resource_type,
    )
    session.add(new_resource)
    await session.flush()
    return new_resource.id


async def get_principal_row_list(session):
    return (
        (await session.execute(sqlalchemy.select(db.models.permission.Principal))).scalars().all()
    )


async def get_resource_row_list(session):
    return (await session.execute(sqlalchemy.select(db.models.permission.Resource))).scalars().all()


async def insert_permissions(session, resource_row_list, principal_row_list):
    for resource_row in resource_row_list:
        permission_count = random.randrange(1, 3)
        sampled_principal_row_list = random.sample(principal_row_list, permission_count)
        for principal_row in sampled_principal_row_list:
            level = random.choice(
                (
                    db.models.permission.PermissionLevel.READ,
                    db.models.permission.PermissionLevel.WRITE,
                    db.models.permission.PermissionLevel.CHANGE,
                )
            )
            await insert_rule(session, resource_row, principal_row, level)


async def insert_rule(session, resource_row, principal_row, permission):
    new_permission = db.models.permission.Rule(
        resource=resource_row,
        principal=principal_row,
        permission=permission,
    )
    session.add(new_permission)
    await session.flush()


RANDOM_SCOPE_TUP = (
    'edi',
    'knb-lter-bes',
    'knb-lter-ble',
    'knb-lter-cap',
    'knb-lter-jrn',
    'knb-lter-kbs',
    'knb-lter-mcm',
    'knb-lter-nin',
    'knb-lter-ntl',
    'knb-lter-nwk',
    'knb-lter-nwt',
    'knb-lter-sbc',
    'knb-lter-vcr',
)

RANDOM_FILE_NAME_TUP = (
    'experiment_results',
    'sample_data',
    'observation_records',
    'climate_data',
    'genomic_sequences',
    'chemical_analysis',
    'species_distribution',
    'cological_surveys',
    'meteorological_data',
    'hydrological_measurements',
    'soil_samples',
    'water_quality',
    'air_quality',
    'biodiversity_index',
    'plant_growth',
    'animal_tracking',
    'microbial_studies',
    'geological_samples',
    'oceanographic_data',
    'paleontological_finds',
    'astronomical_observations',
    'environmental_impact',
    'pollution_levels',
    'radiation_measurements',
    'toxicology_reports',
    'phytoplankton_counts',
    'zooplankton_counts',
    'fish_population',
    'bird_migration',
    'mammal_sightings',
    'insect_collections',
    'fungal_studies',
    'virus_isolates',
    'bacterial_cultures',
    'archaeological_digs',
    'mineral_composition',
    'sediment_analysis',
    'forest_inventory',
    'wetland_surveys',
    'coral_reef_health',
    'algal_blooms',
    'carbon_emissions',
    'greenhouse_gases',
    'energy_consumption',
    'renewable_resources',
    'waste_management',
    'recycling_rates',
    'conservation_efforts',
    'habitat_restoration',
    'endangered_species',
    'climate_change',
    'global_warming',
    'sea_level_rise',
    'glacier_melt',
    'permafrost_thaw',
    'ocean_acidification',
    'deforestation_rates',
    'reforestation_projects',
    'urbanization_impact',
    'agricultural_yields',
    'crop_rotation',
    'pesticide_use',
    'fertilizer_application',
    'irrigation_systems',
    'drought_resistance',
    'flood_control',
    'storm_surge',
    'tsunami_warnings',
    'earthquake_data',
    'volcanic_activity',
    'landslide_risk',
    'wildfire_incidents',
    'hurricane_tracks',
    'tornado_reports',
    'lightning_strikes',
    'solar_radiation',
    'wind_speeds',
    'precipitation_levels',
    'temperature_records',
    'humidity_measurements',
    'barometric_pressure',
    'snowfall_data',
    'ice_core_samples',
    'tree_ring_data',
    'pollen_analysis',
    'lake_sediments',
    'river_flow',
    'groundwater_levels',
    'aquifer_studies',
    'wetland_ecology',
    'peat_bogs',
    'mangrove_forests',
    'seagrass_beds',
    'kelp_forests',
    'deep_sea_exploration',
    'marine_biology',
    'freshwater_ecology',
    'terrestrial_ecology',
    'atmospheric_chemistry',
    'space_weather',
)

RANDOM_PERSON_NAME_LIST = [
    'John Smith',
    'Jane Brown',
    'Michael Johnson',
    'Emily Davis',
    'James Miller',
    'Mary Wilson',
    'Robert Taylor',
    'Linda Anderson',
    'William Thomas',
    'Barbara Jackson',
    'David White',
    'Susan Harris',
    'Richard Martin',
    'Jessica Thompson',
    'Charles Garcia',
    'Sarah Martinez',
    'Joseph Robinson',
    'Karen Clark',
    'Thomas Rodriguez',
    'Nancy Lewis',
    'Christopher Lee',
    'Lisa Walker',
    'Daniel Hall',
    'Betty Allen',
    'Matthew Young',
    # 'Margaret King',
    # 'Anthony Wright',
    # 'Sandra Scott',
    # 'Mark Green',
    # 'Ashley Adams',
    # 'Donald Baker',
    # 'Kimberly Nelson',
    # 'Steven Carter',
    # 'Patricia Mitchell',
    # 'Paul Perez',
    # 'Carol Roberts',
    # 'Andrew Turner',
    # 'Michelle Phillips',
    # 'Joshua Campbell',
    # 'Amanda Parker',
    # 'Kenneth Evans',
    # 'Melissa Edwards',
    # 'Kevin Collins',
    # 'Stephanie Stewart',
    # 'Brian Sanchez',
    # 'Rebecca Morris',
    # 'George Rogers',
    # 'Laura Reed',
    # 'Edward Cook',
    # 'Sharon Morgan',
    # 'Ronald Bell',
    # 'Cynthia Murphy',
    # 'Timothy Bailey',
    # 'Angela Rivera',
    # 'Jason Cooper',
    # 'Brenda Richardson',
    # 'Jeffrey Cox',
    # 'Amy Howard',
    # 'Ryan Ward',
    # 'Anna Torres',
    # 'Jacob Peterson',
    # 'Kathleen Gray',
    # 'Gary Ramirez',
    # 'Shirley James',
    # 'Nicholas Watson',
    # 'Dorothy Brooks',
    # 'Eric Kelly',
    # 'Debra Sanders',
    # 'Stephen Price',
    # 'Frances Bennett',
    # 'Jonathan Wood',
    # 'Gloria Barnes',
    # 'Larry Ross',
    # 'Janet Henderson',
    # 'Justin Coleman',
    # 'Maria Jenkins',
    # 'Scott Perry',
    # 'Heather Powell',
    # 'Brandon Long',
    # 'Diane Patterson',
    # 'Benjamin Hughes',
    # 'Ruth Flores',
    # 'Samuel Washington',
    # 'Jacqueline Butler',
    # 'Gregory Simmons',
    # 'Kathy Foster',
    # 'Frank Gonzales',
    # 'Pamela Bryant',
    # 'Patrick Alexander',
    # 'Katherine Russell',
    # 'Raymond Griffin',
    # 'Christine Diaz',
    # 'Jack Hayes',
    # 'Ann Myers',
    # 'Dennis Ford',
    # 'Alice Hamilton',
    # 'Jerry Graham',
    # 'Julie Sullivan',
    # 'Tyler Wallace',
    # 'Megan West',
]


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
