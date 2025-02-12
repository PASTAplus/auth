#!/usr/bin/env python

"""Fill the collection, resource and permission tables with random data.
"""
import logging
import pathlib
import random
import sys

import sqlalchemy.exc

ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((ROOT_PATH / 'webapp').as_posix())

import db.profile
import db.iface
import db.permission

log = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    session = db.iface.SessionLocal()

    try:
        session.query(db.permission.Permission).delete()
        session.query(db.permission.Resource).delete()
        session.query(db.permission.Collection).delete()
        add_permissions(session)
    except sqlalchemy.exc.SQLAlchemyError as e:
        log.error(f'Error: {e}')
        session.rollback()
        return 1

    session.commit()

    log.info('Collections, resources and permissions have been added')

    return 0

def add_permissions(session):
    for scope in RANDOM_SCOPE_TUP:
        id_count = random.randrange(1, 10)
        id_ = random.randrange(1, 10000)
        for i in range(id_count):
            id_ += random.randrange(1, 100)
            ver_count = random.randrange(1, 10)
            for ver in range(1, ver_count):
                label = f'{scope}.{id_}.{ver}'
                log.info(label)
                package_id = insert_package(session, label)
                # quality report
                insert_entity(
                    session,
                    package_id,
                    'quality_report.xml',
                    'metadata',
                )
                # metadata
                insert_entity(
                    session,
                    package_id,
                    'metadata.eml',
                    'metadata',
                )
                # data
                data_count = random.randrange(1, 10)
                for j in range(data_count):
                    insert_entity(
                        session,
                        package_id,
                        random.choice(RANDOM_FILE_NAME_TUP)
                        + random.choice(('.csv', '.txt', '.jpg', '.tiff')),
                        'data',
                    )
        log.info('')

    profile_id_list = get_profile_id_list(session)
    log.debug(f'profile_id_list: {profile_id_list}')
    # sys.exit()
    resource_id_list = get_resource_id_list(session)
    insert_permissions(session, resource_id_list, profile_id_list)


def insert_package(session, package_label):
    new_collection = db.permission.Collection(
        label=package_label,
        type='package',
    )
    session.add(new_collection)
    session.flush()
    return new_collection.id


def insert_entity(session, package_id, entity_name, entity_type):
    log.debug(f'entity_name: {entity_name}')

    new_resource = db.permission.Resource(
        collection_id=package_id,
        label=entity_name,
        type=entity_type,
    )
    session.add(new_resource)
    session.flush()
    return new_resource.id


def get_profile_id_list(session):
    row_list = session.query(db.profile.Profile.id).all()
    # log.debug(f'profile_id_list: {row_list}')
    return [row[0] for row in row_list]


def get_resource_id_list(session):
    row_list = session.query(db.permission.Resource.id).all()
    # log.debug(f'resource_id_list: {row_list}')
    return [row[0] for row in row_list]


def insert_permission(session, profile_id, resource_id, level):
    new_permission = db.permission.Permission(
        resource_id=resource_id,
        grantee_id=profile_id,
        grantee_type=db.permission.GranteeType.PROFILE,
        level=level,
    )
    session.add(new_permission)
    session.flush()


def insert_permissions(session, resource_id_list, profile_id_list):
    for resource_id in resource_id_list:
        permission_count = random.randrange(1, 3)
        profile_list = random.sample(profile_id_list, permission_count)
        for profile_id in profile_list:
            level = random.choice(
                (
                    db.permission.PermissionLevel.READ,
                    db.permission.PermissionLevel.WRITE,
                    db.permission.PermissionLevel.OWN,
                )
            )
            insert_permission(session, profile_id, resource_id, level)


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

if __name__ == '__main__':
    sys.exit(main())
