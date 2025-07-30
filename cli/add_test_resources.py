#!/usr/bin/env python

"""Fill the Resource and Rule tables with random data."""
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

import util.dependency
import db.models.profile
import db.session
import db.models.permission
import db.models.search

log = daiquiri.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    async with util.dependency.get_session() as session:
        await session.execute(sqlalchemy.delete(db.models.search.RootResource))
        await session.execute(sqlalchemy.delete(db.models.permission.Rule))
        await session.execute(sqlalchemy.delete(db.models.permission.Resource))
        await add_permissions(session)

    log.info('Resources and permissions have been added')

    return 0


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

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
