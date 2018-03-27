{
    'name': 'Website Fix',
    'summary': 'Rediret Fix',
    'description': 'When using odoo cart with another website as a frontend, prevents redirect by odoo controllers',
    'category': 'Website',
    'sequence': 900,
    'version': '1.0',
    'depends': ['website'],
    'data': [
        'views/inherited_website_layout_template.xml',
            ],

    'application': False,
    'author': 'Confianz Global',
}
