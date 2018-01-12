"""
Scrapes data from lego shop (section exclusive sets and saves data to mongodb)
"""

import argparse
import json
import requests
import smtplib

import pymongo

import config

class LegoPriceMonitor:

    def __init__(self, link_to_parse, collection_to_save_to):
        self.link_to_parse = link_to_parse
        self.collection_to_save_to = collection_to_save_to
        self.main_collection = None
        self.docs_properties = ['seo_path','product_code','list_price',
        'on_sale', 'sale_price', 'featured', 'piece_count', 'availability_status',
        'available_date']

        self.load_data()

    def connect_to_db(self):
        f = open(config.MONGO_SECRET_FILE, 'r')
        ulist = f.read().split(',')
        mongo_u = ulist[0].strip()
        mongo_p = ulist[1].strip()
        f.close()

        client = pymongo.MongoClient(config.MONGODB_HOST, config.MONGO_PORT)
        try:
            client['admin'].authenticate(mongo_u, mongo_p, mechanism='SCRAM-SHA-1')
            main_db = client[config.MAIN_DB]
            self.main_collection = main_db[self.collection_to_save_to]
            #print(type(self.main_collection))
        except Exception as e:
            print('mongo db auth error %s' % e)
            return self

    def save_date_to_db(self, data):

        if not self.main_collection:
            self.connect_to_db()

        for el in data:
            doc_to_save = {
                'seo_path': el['seo_path'],
                'product_code': el['product_code'],
                'list_price': el['skus'][0]['list_price'],
                'on_sale': el['skus'][0]['on_sale'],
                'sale_price': el['skus'][0]['sale_price'],
                'featured': el['featured'],
                'piece_count':el['piece_count'],
                'availability_status':el['skus'][0]['general_availability']['availability_status'],
                'available_date':el['skus'][0]['general_availability']['available_date'],
            }

            self.main_collection.insert(doc_to_save)

    def get_items_from_db(self):
        if not self.main_collection:
            self.connect_to_db()

        return self.main_collection.find()

    def check_data_to_update(self, data_to_update):
        data_to_update_checked = []
        for item in data_to_update:
            items_in_db = self.main_collection.find({'product_code': item['product_code']})

            items_are_different = False

            for item_in_db in items_in_db:
                for prop in self.docs_properties:
                    try:
                        if item[prop] != item_in_db[prop]:
                            items_are_different = True
                    except KeyError as e:
                        try:
                            if item['skus'][0][prop] != item_in_db[prop]:
                                items_are_different = True
                        except KeyError as e:
                            if item['skus'][0]['general_availability'][prop] != item_in_db[prop]:
                                items_are_different = True


                        #print(item['skus'][0][prop])

                    # print(item_in_db[prop])


            if items_are_different:
                data_to_update_checked.append(item)

        return data_to_update_checked

    def send_email(self, data_new, data_updated):
        # set up the SMTP server
        server = smtplib.SMTP(host='smtp.gmail.com', port=587)
        server.starttls()
        f = open(config.MAIL_SECRET_FILE, 'r')
        ulist = f.read().split(',')
        mail_u = ulist[0].strip()
        mail_p = ulist[1].strip()
        f.close()
        server.login(mail_u, mail_p)

        from_addr = 'LegoPriceMonitor@davidediblasi.net'
        to_addrs  = ','.join(config.MAIL_RECEIVERS)
        subject = "Lego Price Monitor Update"

        msg = "Subject: {0}\n\n".format(subject)
        msg = msg + "From: {0}\r\nTo: {1}\r\n\r\n".format(from_addr, to_addrs)

        msg = msg + "Nuovi Dati:"
        for d in data_new:
            msg = msg + '\n  {0} | codice: {1}'.format(d['seo_path'], d['product_code'])

        msg = msg + "\nDati Aggiornati:"
        for d in data_updated:
            msg = msg + '\n  {0} | codice: {1}'.format(d['seo_path'], d['product_code'])


        #print(msg)
        server.sendmail(from_addr, to_addrs, msg)
        server.quit()


    def load_data(self):
        resp = requests.get(url=self.link_to_parse)
        data = json.loads(resp.text)

        """
        Result example:

        ----

        {'_links': {'self': {'href': '/sh/rest/products/75192'}},
      'featured': 'exclusiveFlag',
      'general_availability': {'availability_status': 'H_OUT_OF_STOCK',
       'available_date': None},
      'media': 'http://cache.lego.com/e/dynamic/is/image/LEGO/75192?$leaf$',
      'seo_path': 'Millennium Falcon™',
      'piece_count': 7541,
      'product_code': '75192',
      'product_type': 'Standard',
      'rating': 0.0,
      'rating_title': 'Nessuna valutazione',
      'seo_path': 'Millennium-Falcon-75192',
      'skus': [{'general_availability': {'availability_status': 'H_OUT_OF_STOCK',
         'available_date': '2017-12-25'},
        'list_price': 799.99,
        'list_price_formatted': '799,99 €',
        'max_order_quantity': 1,
        'on_sale': False,
        'sale_price': 799.99,
        'sale_price_formatted': '799,99 €',
        'sku_number': '6175770',
        'vip_availability': {'availability_status': 'H_OUT_OF_STOCK',
         'available_date': '2017-12-25'},
        'vip_points': 799}],
      'vip_availability': {'availability_status': 'H_OUT_OF_STOCK',
       'available_date': None}}

       """
        # print('seo_path', 'Code', 'Price', 'On Sale', 'Sale Price', 'Feature', 'Piece', 'Availability', 'available_date', )
        for el in data['results']:
            print(el['seo_path'],
                el['product_code'],
                el['skus'][0]['list_price'],
                el['skus'][0]['on_sale'],
                el['skus'][0]['sale_price'],
                el['featured'],
                el['piece_count'],
                el['skus'][0]['general_availability']['availability_status'],
                el['skus'][0]['general_availability']['available_date'],
            )
            break

        try:
            products_code_known = [item['product_code'] for item in self.get_items_from_db()]
        except TypeError as e:
            print('No data on DB')
            products_code_known = []
            # non ci sono dati

        data_to_save = [item for item in data['results'] if item['product_code'] not in products_code_known]
        data_to_update = [item for item in data['results'] if item['product_code'] in products_code_known]
        data_to_update_checked = []

        if len(data_to_save) > 0:
            self.save_date_to_db(data_to_save)

        if len(data_to_update) > 0:
            data_to_update_checked = self.check_data_to_update(data_to_update)
            self.save_date_to_db(data_to_update_checked)

        if len(data_to_save) > 0 or len(data_to_update_checked) > 0:
            self.send_email(data_to_save, data_to_update_checked)


def main(args):
    print(args)
    lego_price_monitor = LegoPriceMonitor(args.link_to_parse, args.collection_to_save_to)

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--link_to_parse', type=str, default=config.DEFAULT_LINK_TO_PARSE,
                        help='Link to parse data (usually a json from lego shop)')
    parser.add_argument('--collection_to_save_to', type=str, default=config.DEFAULT_COLLECTION_TO_SAVE_TO,
                        help='Collection on which the data collected will be saved to.')
    # parser.add_argument('--threshold', type=float, default=0,
    #                     help='A margin to avoid raising alerts with minor price drops')
    # parser.add_argument('--project', type=int, default=settings.SHUB_PROJ_ID,
    #                     help='Project ID to get info from')

    return parser.parse_args()


if __name__ == '__main__':
    main(parse_args())
