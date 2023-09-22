# Copyright 2023 PingCAP, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from peewee import MySQLDatabase, Model, CharField, IntegerField

from config import Config


def get_db_engine():
    config = Config()
    connect_params = {}
    if config.ca_path:
        connect_params = {
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
            "ssl_ca": config.ca_path,
        }
    return MySQLDatabase(
        config.tidb_db_name,
        host=config.tidb_host,
        port=config.tidb_port,
        user=config.tidb_user,
        password=config.tidb_password,
        **connect_params,
    )


db = get_db_engine()


class BaseModel(Model):
    class Meta:
        database = db


class Player(BaseModel):
    name = CharField(max_length=32, unique=True)
    coins = IntegerField(default=0)
    goods = IntegerField(default=0)

    class Meta:
        table_name = "players"

    def __str__(self):
        return f"Player(name={self.name}, coins={self.coins}, goods={self.goods})"


def simple_example() -> None:
    # create a player, who has a coin and a goods.
    Player.create(name="test", coins=1, goods=1)

    # get this player, and print it.
    player = Player.get(Player.name == "test")
    print(player)

    # create players with bulk inserts.
    # insert 200 players totally, with 50 players per batch.
    # all players have random uuid
    player_list = [Player(name=f"player_{i}", coins=10000, goods=100) for i in range(200)]
    batch_size = 50
    for idx in range(0, len(player_list), batch_size):
        Player.bulk_create(player_list[idx : idx + batch_size])

    # print the number of players
    count = Player.select().count()
    print(f"number of players: {count}")

    # print the first 3 players
    three_players = Player.select().order_by("id").limit(3)
    for player in three_players:
        print(player)


def trade(buyer_id: int, seller_id: int, amount: int, price: int) -> None:
    with db.atomic():
        # open a transaction, use select for update to lock the rows
        buyer = Player.select().where(Player.id == buyer_id).for_update().get()
        if buyer.coins < price:
            print("buyer coins not enough")
            return
        seller = Player.select().where(Player.id == seller_id).for_update().get()
        if seller.goods < amount:
            print("seller goods not enough")
            return
        Player.update(coins=Player.coins - price, goods=Player.goods + amount).where(
            Player.id == buyer_id
        ).execute()
        Player.update(coins=Player.coins + price, goods=Player.goods - amount).where(
            Player.id == seller_id
        ).execute()
        print("trade success")


def trade_example() -> None:
    buyer = Player.create(name="buyer", coins=100, goods=0)
    seller = Player.create(name="seller", coins=0, goods=100)
    buyer_id, seller_id = buyer.id, seller.id

    # buyer wants to buy 10 goods from player 2.
    # it will cost 500 coins, but buyer cannot afford it.
    # so this trade will fail, and nobody will lose their coins or goods
    print("============== trade 1 start =================")
    trade(buyer_id=buyer_id, seller_id=seller_id, amount=10, price=500)
    print("============== trade 1 end ===================")

    # then player 1 has to reduce the incoming quantity to 2.
    # this trade will successful
    print("============== trade 2 start =================")
    trade(buyer_id=buyer_id, seller_id=seller_id, amount=10, price=100)
    print("============== trade 2 end ===================")

    traders = Player.select().where(Player.id.in_((buyer_id, seller_id)))
    for player in traders:
        print(player)


if __name__ == "__main__":
    try:
        db.create_tables([Player])
        simple_example()
        trade_example()
    finally:
        db.drop_tables([Player])
