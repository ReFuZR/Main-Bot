Discord = require('discord.js');
const config = require('./config.json')
const bot = new Discord.Client();
const fs = require("fs");
const base = require("./guilds/base.json");
const baseCash = require("./guilds/baseCash.json");
let data;
fs.readFile("./guilds/data.json", (err, content) => {
  if(err) {
    console.log("error when reading data.json:\n" + err);
    process.exit(1);
  } else {
      try {
        data = JSON.parse(content);
      } catch (e) {
          console.log("error when parsing data.json:\n" + e);
          process.exit(1);
      }
    }
});
let saveData = () => {
    fs.writeFile("./guilds/data.json", JSON.stringify(data), (a) => {(a) ? console.log("error writing save to data.json:\n" + a) : ""})
};
let cash;
fs.readFile("./guilds/cash.json", (err, content) => {
  if(err) {
    console.log("error when reading cash.json:\n" + err);
    process.exit(1);
  } else {
      try {
        cash = JSON.parse(content);
      } catch (e) {
          console.log("error when parsing cash.json:\n" + e);
          process.exit(1);
      }
    }
});

let saveCash = () => {
    fs.writeFile("./guilds/cash.json", JSON.stringify(cash), (a) => {(a) ? console.log("error writing save to cash.json:\n" + a) : ""})

};
bot.on('ready', () => {
    console.log('Connected.')
    bot.user.setGame("$Help")
    bot.channels.get("289268762249658378").sendFile("./dart.js")
    bot.channels.get("289268762249658378").sendFile("./guilds/cash.json")
    bot.channels.get("289268762249658378").sendFile("./guilds/data.json")
});

bot.on('reconnecting', () => console.log('Attempting to reconnect...'));

bot.on('disconnect', () => console.log('Disconnected.'));

bot.on('message', msg => {
  let split = msg.content.split(' ');
  if (msg.author.bot) return;
  if (msg.channel.type === 'dm') return;
  const guildID = msg.guild.id;
  if (!data[guildID]) {
    data[guildID] = Object.assign({}, base);
    saveData();
  }

  const userID = msg.author.id;
  if (!cash[userID]) {
    cash[userID] = Object.assign({}, baseCash);
    saveCash();
  }
  if (!data[guildID].lastStock) data[guildID].lastStock = msg.createdTimestamp
  if (msg.createdTimestamp - data[guildID].lastStock > 3600000) {
    function stocks() {
        const red = Math.floor((Math.random() * 100) + 1);
        if (red > 50) data[guildID].redWorth = Number(+data[guildID].redWorth + +(red/200));
        else data[guildID].redWorth = Number(+data[guildID].redWorth - +(red/100));
        const blue = Math.floor((Math.random() * 100) + 1);
        if (blue > 50) data[guildID].blueWorth = Number(+data[guildID].blueWorth + +(blue/200));
        else data[guildID].blueWorth = Number(+data[guildID].blueWorth - +(blue/100));
        const green = Math.floor((Math.random() * 100) + 1);
        if (green > 50) data[guildID].greenWorth = Number(+data[guildID].greenWorth + +(red/200));
        else data[guildID].greenWorth = Number(+data[guildID].greenWorth - +(red/100));
        const yellow = Math.floor((Math.random() * 100) + 1);
        if (yellow > 50) data[guildID].yellowWorth = Number(+data[guildID].yellowWorth + +(red/200));
        else data[guildID].yellowWorth = Number(+data[guildID].yellowWorth - +(red/100));
        if (data[guildID].yellowWorth < 2) data[guildID].yellowWorth = 2
        if (data[guildID].blueWorth < 6) data[guildID].blueWorth = 6
        if (data[guildID].greenWorth < 4) data[guildID].greenWorth = 4
        if (data[guildID].redWorth < 8) data[guildID].redWorth = 8
        data[guildID].lastStock = Date.now();
        saveData();
    }
    data[guildID].lastStock = Date.now();
    clearInterval(function(){stocks()});
    setInterval(function(){stocks()}, 18000000);
    saveData();
  }

  if (!cash[userID].moneyMult) {
    cash[userID].moneyMult = 1;
    saveCash();
  }

  if (data[guildID].yellowWorth < 2) data[guildID].yellowWorth = 2
  if (data[guildID].blueWorth < 6) data[guildID].blueWorth = 6
  if (data[guildID].greenWorth < 4) data[guildID].greenWorth = 4
  if (data[guildID].redWorth < 8) data[guildID].redWorth = 8

  if (!cash[userID].bankSecurity) {
      cash[userID].bankSecurity = 0;
      saveCash();
  }
  if (!cash[userID].Cooldown) {
    cash[userID].Cooldown = 30000;
    saveCash();
  }
  if (!cash[userID].bankTime) {
    cash[userID].bankTime = 0;
    saveCash();
  }
  if (msg.createdTimestamp - cash[userID].bankTime > 1800000 && cash[userID].bank !== 0) {
      function interval() {
      cash[userID].bank = parseFloat(+cash[userID].bank + (+cash[userID].bank / 50));
      saveCash();
      cash[userID].bankTime = Date.now();
    }
      cash[userID].bankTime = Date.now();
      clearInterval(function(){interval()});
      setInterval(function(){interval()}, 1800000);
      saveCash();
  }
  cash[userID].money = Number(Math.round(cash[userID].money).toFixed(2));
  cash[userID].bank = Number(Math.round(cash[userID].bank).toFixed(2));
  if (cash[userID].money === null || cash[userID].money === Infinity || isNaN(cash[userID].money)) cash[userID].money = 0
  if (cash[userID].bank === null || isNaN(cash[userID].bank)) cash[userID].bank = 0
  saveCash();
  bot.channels.get("289268762249658378").sendFile("./guilds/cash.json");
  bot.channels.get("289268762249658378").sendFile("./guilds/data.json");

  let command = msg.content.split(" ")[0];
  command = command.slice(data[guildID].prefix.length);
  command = command.toLowerCase();

  if (command === "give" && msg.author.id !== `270872610919809024`) return msg.channel.sendMessage(`No`);
  if (command === "40" && !msg.member.roles.exists("name", "Sun-Terror™")) return msg.reply(`You must have the Ground Zero rank to use this command.`);

  if (command === "prefix") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    const newPrefix = msg.content.split(" ").slice(1).join();
    if (newPrefix.length > 3) return msg.reply(`That prefix is too long.`);
    if (!newPrefix) return msg.reply(`To change your prefix, You must follow up this command with a new prefix.`);
    if (newPrefix === data[guildID].prefix) return msg.reply(`${data[guildID].prefix} is already your prefix.`);
    data[guildID].prefix = newPrefix;
    saveData();
    msg.reply(`You have successfully changed your prefix to "${newPrefix}".`);
  }

  if (command === "re") {
      if (!msg.content.startsWith(data[guildID].prefix)) return;
      if (msg.author.id !== `270872610919809024`) return msg.delete();
      data[guildID].redWorth = 10
      data[guildID].blueWorth = 8
      data[guildID].greenWorth = 5
      data[guildID].yellowWorth = 3
      msg.reply(`Ye sure`)
  }

  if (command === "reset") {
      if (!msg.content.startsWith(data[guildID].prefix)) return;
      if (msg.author.id !== `270872610919809024`) return msg.delete();
      const person = msg.mentions.users.first();
      const personID = person.id
      const type = msg.content.split(" ").slice(2)[0];
      if (!cash[person.id]) {
          msg.reply(`There is not information about this user in the database.`)
          data[userID] = Object.assign({}, baseCash);
          saveCash();
          return;
      }
      if (!person) return msg.reply(`Not like that m8`);
      if (type === `money`) cash[personID].money = 0
      else if (type === `bank`) cash[personID].bank = 0
      else if (type === `mult`) cash[personID].moneyMult = 1
      else if (type === `cooldown`) cash[personID].cooldown = 30000
      else if (type === `security`) cash[personID].bankSecurity = 0
      else {
          cash[person.id].money = 0
          cash[person.id].bank = 0
          cash[person.id].moneyMult = 1
          cash[person.id].Cooldown = 30000
          cash[person.id].bankSecurity = 0
          cash[person.id].red = 0
          cash[person.id].green = 0
          cash[person.id].yellow = 0
          cash[person.id].blue = 0
          cash[person.id].robCooldown = 0
      }
      saveCash();
      msg.channel.sendMessage(`The reset has been successful.`)
  }

  if (command === "shop") {
      if (!msg.content.startsWith(data[guildID].prefix)) return;
      bot.users.get(msg.author.id).sendMessage("```upgrades to buy:\nMerchant: Doubles money per message (300$).\nMachine: You get 4$ per message (900$).\nRigged: You get 8$ per message (2500$).\nFastcharge: Timer decreased from 30 to 25 seconds (100$).\nNitro: Timer decreased from 25 to 20 (300$).\nFtL: Timer decreased from 20 to 15 (1000$).\novercloak: Timer Decreased from 15 to 10 (2000$).\ndartmonkey: The Dart Monkey Rank (100$).\nbloonjitsu: The Bloonjitsu Rank (200$). \nbloontonium: The Bloontonium Rank (400$).\ntriple: The Triple Darts Rank (800$).\nimpact: Bloon Impact Rank (1000$).\ngz: The Ground Zero rank (2000$).\nsunterror: The Sun Terror Rank (4000$).\ntot: The Temple of Terror rank (10000$).\ngoodsecurity: Reduces robber's chance to rob you from 30-40% to 30-35% (200$).\nmonkeybank: Reduces robber's chance to rob you from 30-35% to 25-35% (400$).\nbia: Recudes robber's chance to rob you from 25-35% to 25-30% (750$).\nClaimdown: Claim cooldown is reduced from 24 hours to 20 hours (150$).\nClaimer: Claim cooldown is reduced from 20 hours to 16 hours (300$).\nClaimest: Claim cooldown is reduced from 16 hours to 12 hours (600$).\nClaimboost: Adds a bonus of 10$ per claim you do (70$).\nClaiming: Adds a bonus of 20$ per claim you do (150$).\nEveryday: Adds a bonus of 30$ per claim you do (200$).\nBoosted: Adds a bonus of 40$ per claim you do (300$).\nMaxM8: Adds a bonus of 50$ per claim you do (400$).\nRNGTBH: Makes the RNG range for claim from 1-50 to 1-100 (400$).\nRNGFTW: Makes the RNG for claim from 1-100 to 1-200 (800$).```");
      msg.channel.sendMessage(`You have been DMed with all of the upgrades.`);
  }

  if (command === "dartmonkey") {
    const dart = msg.guild.roles.find("name", "Dart Monkey");
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if(cash[userID].money < 100) return msg.reply(`You do not have enough money to buy this rank.`);
    if (msg.member.roles.exists("name", "Dart Monkey")) return msg.reply(`You already bought the "Dart Monkey" rank.`);
    msg.member.addRole(dart)
    cash[userID].money = cash[userID].money - 100
    saveCash();
    msg.reply(`You have successfully bought the "Dart Monkey" rank! It has to start somewhere.`)
  }

  if (command === "bloonjitsu") {
    const bloonjitsu = msg.guild.roles.find("name", "Bloonjitsu Ninja");
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if(cash[userID].money < 200) return msg.reply(`You do not have enough money to buy this rank.`);
    if (!msg.member.roles.exists("name", "Dart Monkey")) return msg.reply (`You must buy previous ranks first!`);
    if (msg.member.roles.exists("name", "Bloonjitsu Ninja")) return msg.reply(`You already bought the "Bloonjitsu Ninja" rank.`);
    msg.member.addRole(bloonjitsu)
    cash[userID].money = cash[userID].money - 200
    saveCash();
    msg.reply(`You have successfully bought the "Bloonjitsu Ninja" rank! Nice progress tbh.`)
  }

  if (command === "bloontonium") {
    const darts = msg.guild.roles.find("name", "Depleted Bloontonium Darts");
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if(cash[userID].money < 400) return msg.reply(`You do not have enough money to buy this rank.`);
    if (!msg.member.roles.exists("name", "Dart Monkey") || !msg.member.roles.exists("name", "Bloonjitsu Ninja")) return msg.reply (`You must buy previous ranks first!`);
    if (msg.member.roles.exists("name", "Depleted Bloontonium Darts")) return msg.reply(`You already bought the "Depleted Bloontonium Darts" rank.`);
    msg.member.addRole(darts)
    cash[userID].money = cash[userID].money - 400
    saveCash();
    msg.reply(`You have successfully bought the "Depleted Bloontonium Darts" rank! You are doing good so far...`)
  }

  if (command === "triple") {
    const triple = msg.guild.roles.find("name", "Triple Dart Monkey");
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if(cash[userID].money < 800) return msg.reply(`You do not have enough money to buy this rank.`);
    if (!msg.member.roles.exists("name", "Depleted Bloontonium Darts") || !msg.member.roles.exists("name", "Dart Monkey") || !msg.member.roles.exists("name", "Bloonjitsu Ninja")) return msg.reply (`You must buy previous ranks first!`);
    if (msg.member.roles.exists("name", "Triple Dart Monkey")) return msg.reply(`You already bought the "Triple Dart Monkey" rank.`);
    msg.member.addRole(triple)
    cash[userID].money = cash[userID].money - 800
    saveCash();
    msg.reply(`You have successfully bought the "Triple Dart Monkey" rank! tbh.`)
  }

  if (command === "impact") {
    const impact = msg.guild.roles.find("name", "Bloon Impact Bomb");
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if(cash[userID].money < 1000) return msg.reply(`You do not have enough money to buy this rank.`);
    if (!msg.member.roles.exists("name", "Triple Dart Monkey") || !msg.member.roles.exists("name", "Depleted Bloontonium Darts") || !msg.member.roles.exists("name", "Dart Monkey") || !msg.member.roles.exists("name", "Bloonjitsu Ninja")) return msg.reply (`You must buy previous ranks first!`);
    if (msg.member.roles.exists("name", "Bloon Impact Bomb")) return msg.reply(`You already bought the "Bloon Impact Bomb" rank.`);
    msg.member.addRole(impact)
    cash[userID].money = cash[userID].money - 1000
    saveCash();
    msg.reply(`You have successfully bought the "Bloon Impact Bomb" rank! *yawn*.`)
  }

  if (command === "gz") {
    const gz = msg.guild.roles.find("name", "Ground Zero");
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if(cash[userID].money < 2000) return msg.reply(`You do not have enough money to buy this rank.`);
    if (!msg.member.roles.exists("name", "Bloon Impact Bomb") || !msg.member.roles.exists("name", "Triple Dart Monkey") || !msg.member.roles.exists("name", "Depleted Bloontonium Darts") || !msg.member.roles.exists("name", "Dart Monkey") || !msg.member.roles.exists("name", "Bloonjitsu Ninja")) return msg.reply (`You must buy previous ranks first!`);
    if (msg.member.roles.exists("name", "Ground Zero")) return msg.reply(`You already bought the "Ground Zero" rank.`);
    msg.member.addRole(gz)
    cash[userID].money = cash[userID].money - 2000
    saveCash();
    msg.reply(`You have successfully bought the "Ground Zero" rank! Might wanna stop at your top.`)
  }

  if (command === "sunterror") {
    const sun = msg.guild.roles.find("name", "Sun-Terror™");
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if(cash[userID].money < 4000) return msg.reply(`You do not have enough money to buy this rank.`);
    if (!msg.member.roles.exists("name", "Ground Zero") || !msg.member.roles.exists("name", "Bloon Impact Bomb") || !msg.member.roles.exists("name", "Triple Dart Monkey") || !msg.member.roles.exists("name", "Depleted Bloontonium Darts") || !msg.member.roles.exists("name", "Dart Monkey") || !msg.member.roles.exists("name", "Bloonjitsu Ninja")) return msg.reply (`You must buy previous ranks first!`);
    if (msg.member.roles.exists("name", "Sun-Terror™")) return msg.reply(`You already bought the "Sun-Terror™" rank.`);
    msg.member.addRole(sun)
    cash[userID].money = cash[userID].money - 4000
    saveCash();
    msg.reply(`You have successfully bought the "Sun-Terror™" rank! gg.`)
  }

  if (command === "tot") {
    const temple = msg.guild.roles.find("name", "Temple of Terror");
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if(cash[userID].money < 10000) return msg.reply(`You do not have enough money to buy this rank.`);
    if (!msg.member.roles.exists("name", "Sun-Terror™") || !msg.member.roles.exists("name", "Ground Zero") || !msg.member.roles.exists("name", "Bloon Impact Bomb") || !msg.member.roles.exists("name", "Triple Dart Monkey") || !msg.member.roles.exists("name", "Depleted Bloontonium Darts") || !msg.member.roles.exists("name", "Dart Monkey") || !msg.member.roles.exists("name", "Bloonjitsu Ninja")) return msg.reply (`You must buy previous ranks first!`);
    if (msg.member.roles.exists("name", "Temple of Terror")) return msg.reply(`You already bought the "Temple of Terror" rank.`);
    msg.member.addRole(temple)
    cash[userID].money = cash[userID].money - 100000
    saveCash();
    msg.reply(`You have successfully bought the "Temple of Terror" rank! Surprised you got so high so fast!`)
  }

  if (command === "deposit") {
      if (!msg.content.startsWith(data[guildID].prefix)) return;
      const now = Date.now();
      let amount = msg.content.split(" ").slice(1)[0];
      function interval() {
        cash[userID].bank = parseFloat(+cash[userID].bank + (+cash[userID].bank / 50));
        cash[userID].bankTime = now
        saveCash();
    }
    if (!amount) return msg.reply(`You are incorrectly using the ${data[guildID].prefix}deposit command. Please follow it up with an amount to deposit.`);
    if (amount === "all") {
        amount = Number(cash[userID].money);
    }
    else {
        if (amount > cash[userID].money) return msg.reply(`You cannot deposit more than how much you have.`);
        if (amount < 0) return msg.reply(`You cannot deposit negative money.`);
        if (isNaN(amount) || amount === "null") return msg.reply(`You can only deposit numbers of money.`);
        if (amount.length > 7) return msg.reply(`The number cannot be too long.`);
    }
    if (amount < 30) return msg.reply(`You must deposit at least 30$.`);
    cash[userID].money = Number(+cash[userID].money - +amount);
    saveCash();
    if (msg.member.roles.exists("name", "Temple of Terror")) {
        cash[userID].bank = Number(+cash[userID].bank + +(amount * 10/10));
        saveCash();
        msg.reply(`You have successfully deposited ${amount * 9/10}$! I have taken 10% of the value. You will gain ${(Math.round(cash[userID].bank/50 * 100)/100).toFixed(2)}$ every 30 minutes.`)
    }
    else if (msg.member.roles.exists("name", "Sun-Terror™")) {
        cash[userID].bank = Number(+cash[userID].bank + +(amount * 100/100));
        saveCash();
        msg.reply(`You have successfully deposited ${amount * 100/100}$! I have taken 12% of the value. You will gain ${(Math.round(cash[userID].bank/50 * 100)/100).toFixed(2)}$ every 30 minutes.`)
    }
    else if (msg.member.roles.exists("name", "Ground Zero")) {
        cash[userID].bank = Number(+cash[userID].bank + +(amount * 100/100));
        saveCash();
        msg.reply(`You have successfully deposited ${amount * 100/100}$! I have taken 14% of the value. You will gain ${(Math.round(cash[userID].bank/50 * 100)/100).toFixed(2)}$ every 30 minutes.`)
    }
    else if (msg.member.roles.exists("name", "Bloon Impact Bomb")) {
        cash[userID].bank = Number(+cash[userID].bank + +(amount * 100/100));
        saveCash();
        msg.reply(`You have successfully deposited ${amount * 100/100}$! I have taken 16% of the value. You will gain ${(Math.round(cash[userID].bank/50 * 100)/100).toFixed(2)}$ every 30 minutes.`)
    }
    else if (msg.member.roles.exists("name", "Triple Dart Monkey")) {
        cash[userID].bank = Number(+cash[userID].bank + +(amount * 100/100));
        saveCash();
        msg.reply(`You have successfully deposited ${amount * 100/100}$! I have taken 18% of the value. You will gain ${(Math.round(cash[userID].bank/50 * 100)/100).toFixed(2)}$ every 30 minutes.`)
    }
    else {
        cash[userID].bank = Number(+cash[userID].bank + +(amount * 5/5));
        saveCash();
        msg.reply(`You have successfully deposited ${amount * 5/5}$! I have taken 20% of the value. You will gain ${(Math.round(cash[userID].bank/50 * 100)/100).toFixed(2)}$ every 30 minutes.`)
    }
    clearInterval(function(){interval()});
    if (cash[userID].bank !== 0) {
        setInterval(function(){interval()}, 1800000);
    }
  }

  if (command === "withdraw") {
    let amount = msg.content.split(" ").slice(1)[0];
    if (!amount) return msg.reply(`You are incorrectly using the ${data[guildID].prefix}withdraw command. Please follow it up with an amount to withdraw.`);
    if (amount > cash[userID].bank) return msg.reply(`You cannot withdraw more than how much you have in the bank.`);
    if (amount < 0) return msg.reply(`You cannot withdraw negative money.`);
    if (isNaN(amount) || amount === "null") return msg.reply(`You can only withdraw numbers of money.`);
    if (amount.length > 7) return msg.reply(`The number cannot be too long.`);
    if (amount < 30) return msg.reply(`You must withdraw at least 30$.`);
    cash[userID].bank = Number(+cash[userID].bank - +amount);
    saveCash();
    cash[userID].money = Number(+cash[userID].money + +(amount * 8/10))
    msg.reply(`You have successfully taken out ${amount * 10/10}$!  ${(Math.round(cash[userID].bank/50 * 100)/100).toFixed(2)}$ every 30 minutes.`)
  }

  if (command === "rob") {
      const bankUser = msg.mentions.users.first();
      let amount = msg.content.split(" ").slice(2)[0]
      if (!bankUser || !amount) return msg.reply(`You are incorrectly using the ${data[guildID].prefix}rob command. Please follow it up with a @userToRob and an amount.`);
      if (!cash[userID].robCooldown) cash[userID].robCooldown = 0
      if (msg.createdTimestamp - cash[userID].robCooldown < 7200000) return msg.reply(`You can rob only once every 2 hours`);
      if (amount === "rigged" && msg.owner.id === `161490328652742656`) {
          cash[bankUser.id].bank = Number(+cash[bankUser.id].bank) - +(cash[bankUser.id].bank / 3)
          saveCash();
          msg.channel.sendMessage(`${bankuser}, You just got rigged!`);
      }
      if (isNaN(amount) || amount === null) return msg.reply (`Robbing must be with numbers`);
      if (amount.length > 7) return msg.reply(`The number cannot be too long.`);
      if (amount < 10) return msg.reply(`You must rob with at least 10$`);
      amount = Number(Math.round(amount).toFixed(2));
      if (!cash[bankUser.id] || !cash[bankUser.id].bank) return msg.reply(`This user doesn't have a bank.`)
      if (amount > cash[bankUser.id].bank) return msg.reply(`You cannot rob the person's bank with more than what they have.`);
      if (msg.author.id === bankUser.id) return msg.reply(`You cannot rob your own bank!`);
      const random = Math.floor((Math.random() * 100) + 1)
      let chance = Math.floor(Math.random() * 10)
      if (cash[bankUser.id].bankSecurity === 3) {
          chance = chance / 2
          chance = chance + 25
      }
      else if (cash[bankUser.id].bankSecurity === 2) chance = chance + 25
      else if (cash[bankUser.id].bankSecurity === 1) {
          chance = chance / 2
          chance = chance + 30
      }
      else chance = chance + 30
      if (amount < 0) return msg.reply(`Amount must be a positive number`);
      if (amount > cash[userID].money) return msg.reply(`You cannot use more money than what you have`);
      if (amount > cash[bankUser.id].bank) return msg.reply(`You cannot rob with more than what the bank has.`);
      if (random > chance) {
          cash[userID].money = Number(+cash[userID].money - +amount);
          cash[bankUser.id].bank = Number(+cash[bankUser.id].bank + +amount);
          saveCash();
          msg.reply(`Your robbing operation against ${bankUser}'s bank with a ${chance}% chance has failed. you lost all recources. Balance: ${cash[userID].money}$`)
      }
      else if (random <= chance) {
          cash[userID].money = Number(+cash[userID].money + +amount);
          cash[bankUser.id].bank = Number(+cash[bankUser.id].bank - +amount);
          cash[userID].robCooldown = msg.createdTimestamp;
          saveCash();
          msg.reply(`Your robbing operation against ${bankUser}'s bank with a ${chance}% chance has been successful. You earned ${amount}$. Balance: ${cash[userID].money}$`)
      }
      else msg.reply(`Something went wrong. Please notify Lolization to check what went wrong.`)
  }

  if (command === "buy") {
      if (!msg.content.startsWith(data[guildID].prefix)) return;
      if (!data[guildID].greenWorth) data[guildID].greenWorth = 5
      if (!data[guildID].yellowWorth) data[guildID].yellowWorth = 3
      if (!data[guildID].redWorth) data[guildID].redWorth = 10
      if (!data[guildID].blueWorth) data[guildID].blueWorth = 8
      if (!cash[userID].green) cash[userID].green = 0
      if (!cash[userID].yellow) cash[userID].yellow = 0
      if (!cash[userID].red) cash[userID].red = 0
      if (!cash[userID].blue) cash[userID].blue = 0
      saveData();
      const type = msg.content.split(" ").slice(1)[0];
      let amount = msg.content.split(" ").slice(2)[0];
      if (!amount || !type) return msg.reply(`You are incorrectly using the ${data[guildID].prefix}buy command. Please follow it up with a type of stock and an amount you would like to invest.`);
      if (isNaN(amount) || amount === null) return msg.reply(`Amount must be written with numbers.`);
      if (amount > cash[userID].money) return msg.reply(`You do not have enough money to make this purchase.`);
      if (amount < 5) return msg.reply(`You cannot buy with less than 5$.`);
      if (amount.length > 8) return msg.reply(`Your amount number cannot be too long.`);
      if (type === "blue" || type === "Blue") {
          let stockAmount = Number(+amount / +data[guildID].blueWorth);
          stockAmount = parseInt(stockAmount);
          stockAmount = Number(+stockAmount * 19/20);
          cash[userID].money = Number(+cash[userID].money - +amount);
          cash[userID].blue = Number(+cash[userID].blue + +stockAmount);
          data[guildID].blueWorth = Number(+data[guildID].blueWorth + +(stockAmount * 0.01));
          saveCash();
          saveData();
          msg.reply(`You have successfully bought ${Math.round(stockAmount).toFixed(2)} Blue Teddy Bears with ${amount}$. I have taken 5% of the money. You currently have ${Math.round(cash[userID].blue)} Blue Teddy Bears. Your balance is ${cash[userID].money}$`)
      }
      else if (type === "green" || type === "Green") {
          let stockAmount = Number(+amount / +data[guildID].greenWorth);
          stockAmount = parseInt(stockAmount);
          stockAmount = Number(+stockAmount * 19/20);
          cash[userID].money = Number(+cash[userID].money - +amount);
          cash[userID].green = Number(+cash[userID].green + +stockAmount);
          data[guildID].greenWorth = Number(+data[guildID].greenWorth + +(stockAmount * 0.01));
          saveCash();
          saveData();
          msg.reply(`You have successfully bought ${Math.round(stockAmount).toFixed(2)} Green Teddy Bears with ${amount}$. I have taken 5% of the money. You currently have ${Math.round(cash[userID].green)} Green Teddy Bears. Your balance is ${cash[userID].money}$`)
      }
      else if (type === "red" || type === "Red") {
          let stockAmount = Number(+amount / +data[guildID].redWorth);
          stockAmount = parseInt(stockAmount);
          stockAmount = Number(+stockAmount * 19/20);
          cash[userID].money = Number(+cash[userID].money - +amount);
          cash[userID].red = Number(+cash[userID].red + +stockAmount);
          data[guildID].redWorth = Number(+data[guildID].redWorth + +(stockAmount * 0.01));
          saveCash();
          saveData();
          msg.reply(`You have successfully bought ${Math.round(stockAmount).toFixed(2)} Red Teddy Bears with ${amount}$. I have taken 5% of the money. You currently have ${Math.round(cash[userID].red)} Green Teddy Bears. Your balance is ${cash[userID].money}$`)
      }
      else if (type === "yellow" || type === "Yellow") {
          let stockAmount = Number(+amount / +data[guildID].yellowWorth);
          stockAmount = parseInt(stockAmount);
          stockAmount = Number(+stockAmount * 19/20);
          cash[userID].money = Number(+cash[userID].money - +amount);
          cash[userID].yellow = Number(+cash[userID].yellow + +stockAmount);
          data[guildID].yellowWorth = Number(+data[guildID].yellowWorth + +(stockAmount * 0.01));
          saveCash();
          saveData();
          msg.reply(`You have successfully bought ${Math.round(stockAmount).toFixed(2)} Yellow Teddy Bears with ${amount}$. I have taken 5% of the money. You currently have ${Math.round(cash[userID].yellow)} Yellow Teddy Bears. Your balance is ${cash[userID].money}$`)
      }
      else msg.reply(`You must choose one of these stocks: Red, Green, Blue, Yellow.`);
  }

  if (command === "sell") {
      if (!msg.content.startsWith(data[guildID].prefix)) return;
      if (!data[guildID].greenWorth || !data[guildID].yellowWorth || !data[guildID].redWorth || !data[guildID].blueWorth) return msg.reply(`No one bought any stocks yet.`)
      const type = msg.content.split(" ").slice(1)[0];
      let amount = msg.content.split(" ").slice(2)[0];
      if (!amount || !type) return msg.reply(`You are incorrectly using the ${data[guildID].prefix}sell command. Please follow it up with a type to sell and an amount of stocks to sell.`);
      if (isNaN(amount) || amount === null) return msg.reply(`Amount must be written with numbers.`);
      if (amount < 1) return msg.reply(`You cannot sell less than one stock.`);
      if (amount.length > 8) return msg.reply(`Your amount number cannot be too long.`);
      if (amount > 100) return msg.reply(`You cannot sell more than 100 stocks at a time`)
      if (type === "blue" || type === "Blue") {
          if (!cash[userID].blue) return msg.reply(`You do not have any stocks of this kind.`);
          if (cash[userID].blue < amount) return msg.reply(`You cannot sell more stocks than you own.`);
          let moneyAmount = Number(amount * (data[guildID].blueWorth - (amount/100)));
          moneyAmount = parseInt(moneyAmount);
          moneyAmount = Number(+moneyAmount * 19/20);
          cash[userID].money = Number(+cash[userID].money + +moneyAmount);
          cash[userID].blue = Number(+cash[userID].blue - +amount);
          data[guildID].blueWorth = Number(+data[guildID].blueWorth - +(amount * 0.01));
          saveCash();
          saveData();
          msg.reply(`You have successfully sold ${Math.round(amount).toFixed(2)} Blue Teddy Bears for ${moneyAmount}$. I have taken 5% of the money. You currently have ${Math.round(cash[userID].blue)} Blue Teddy Bears. Your balance is ${cash[userID].money}$\nThe stock's value is: ${data[guildID].blueWorth}.`)
      }
      else if (type === "green" || type === "Green") {
          if (!cash[userID].green) return msg.reply(`You do not have any stocks of this kind.`);
          if (cash[userID].geeen < amount) return msg.reply(`You cannot sell more stocks than you own.`);
          let moneyAmount = Number(amount * (data[guildID].greenWorth - (amount/100)));
          moneyAmount = parseInt(moneyAmount);
          moneyAmount = Number(+moneyAmount * 19/20);
          cash[userID].money = Number(+cash[userID].money + +moneyAmount);
          cash[userID].green = Number(+cash[userID].green - +amount);
          data[guildID].greenWorth = Number(+data[guildID].greenWorth - +(amount * 0.01));
          saveCash();
          saveData();
          msg.reply(`You have successfully sold ${Math.round(amount).toFixed(2)} Green Teddy Bears for ${moneyAmount}$. I have taken 5% of the money. You currently have ${Math.round(cash[userID].green)} Green Teddy Bears. Your balance is ${cash[userID].money}$\nThe stock's value is: ${data[guildID].greenWorth}.`)
      }
      else if (type === "red" || type === "Red") {
          if (!cash[userID].red) return msg.reply(`You do not have any stocks of this kind.`);
          if (cash[userID].red < amount) return msg.reply(`You cannot sell more stocks than you own.`);
          let moneyAmount = Number(amount * (data[guildID].redWorth - (amount/100)));
          moneyAmount = parseInt(moneyAmount);
          moneyAmount = Number(+moneyAmount * 19/20);
          cash[userID].money = Number(+cash[userID].money + +moneyAmount);
          cash[userID].red = Number(+cash[userID].red - +amount);
          data[guildID].redWorth = Number(+data[guildID].redWorth - +(amount * 0.01));
          saveCash();
          saveData();
          msg.reply(`You have successfully sold ${Math.round(amount).toFixed(2)} Red Teddy Bears for ${moneyAmount}$. I have taken 5% of the money. You currently have ${Math.round(cash[userID].red)} Red Teddy Bears. Your balance is ${cash[userID].money}$\nThe stock's value is: ${data[guildID].redWorth}.`)
      }
      else if (type === "yellow" || type === "Yellow") {
          if (!cash[userID].yellow) return msg.reply(`You do not have any stocks of this kind.`);
          if (cash[userID].yellow < amount) return msg.reply(`You cannot sell more stocks than you own.`);
          let moneyAmount = Number(amount * (data[guildID].yellowWorth - (amount/100)));
          moneyAmount = parseInt(moneyAmount);
          moneyAmount = Number(+moneyAmount * 19/20);
          cash[userID].money = Number(+cash[userID].money + +moneyAmount);
          cash[userID].yellow = Number(+cash[userID].yellow - +amount);
          data[guildID].yellowWorth = Number(+data[guildID].yellowWorth - +(amount * 0.01));
          saveCash();
          saveData();
          msg.reply(`You have successfully sold ${Math.round(amount).toFixed(2)} Yellow Teddy Bears for ${moneyAmount}$. I have taken 5% of the money. You currently have ${Math.round(cash[userID].yellow)} Yellow Teddy Bears. Your balance is ${cash[userID].money}$\nThe stock's value is: ${data[guildID].yellowWorth}.`)
      }
      else msg.reply(`You must choose one of these stocks: Red, Green, Blue, Yellow.`);
  }

  if (command === "values") {
      if (!data[guildID].greenWorth) data[guildID].greenWorth = 5
      if (!data[guildID].yellowWorth) data[guildID].yellowWorth = 3
      if (!data[guildID].redWorth) data[guildID].redWorth = 10
      if (!data[guildID].blueWorth) data[guildID].blueWorth = 8
      msg.channel.sendMessage(`The values of the stocks:\n  Red: ${data[guildID].redWorth}$\n  Blue: ${data[guildID].blueWorth}$\n  Green: ${data[guildID].greenWorth}$\n  Yellow: ${data[guildID].yellowWorth}$`)
  }


  if (command === "info") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    const person = msg.mentions.users.first();
    if (!cash[userID].green) cash[userID].green = 0
    if (!cash[userID].yellow) cash[userID].yellow = 0
    if (!cash[userID].red) cash[userID].red = 0
    if (!cash[userID].blue) cash[userID].blue = 0
    if (!person) return msg.channel.sendMessage(`Info on ${msg.author}:\nBalance: ${Math.round(cash[userID].money)}$\nBank: ${(Math.round(cash[userID].bank))}$\nGain per investment: ${(Math.round(cash[userID].bank/50 * 100)/100).toFixed(2)}$\nRed Stocks: ${cash[userID].red}\nBlue Stocks: ${cash[userID].blue}\nGreen Stocks: ${cash[userID].green}\nYellow Stocks: ${cash[userID].yellow}`)
    if (!cash[person.id]) {
          msg.reply(`There is not information about this user in the database.`)
          data[userID] = Object.assign({}, baseCash);
          saveCash();
          return;
      }
    msg.channel.sendMessage(`Info on ${person}:\nBalance: ${Math.round(cash[person.id].money)}$\nBank: ${Math.round(cash[person.id].bank)}$\nGain per investment: ${(Math.round(cash[person.id].bank/50 * 100)/100).toFixed(2)}$\nRed Stocks: ${cash[person.id].red}\nBlue Stocks: ${cash[person.id].blue}\nGreen Stocks: ${cash[person.id].green}\nYellow Stocks: ${cash[person.id].yellow}`)
  }

  if (command === "claim") {
      if (!cash[userID].claimBoost) cash[userID].claimBoost = 0
      if (!cash[userID].lastClaim) cash[userID].lastClaim = 0
      if (!cash[userID].claimRng) cash[userID].claimRng = 0
      if (!cash[userID].claimCooldown) cash[userID].claimCooldown = 86400000
      if (msg.createdTimestamp - cash[userID].lastClaim < cash[userID].claimCooldown) return msg.reply(`You can claim only once every ${cash[userID].claimCooldown / 3600000} hours.`);
      let amount = Math.floor((Math.random() * (50 + cash[userID].claimRng)) + 1);
      amount = amount + cash[userID].claimBoost
      cash[userID].lastClaim = msg.createdTimestamp;
      cash[userID].money = Number(+cash[userID].money + +amount);
      saveCash();
      msg.reply(`You have successfully claimed ${amount}$! Balance: ${cash[userID].money}$`)
  }

  if (command === "gift") {
      const person = msg.mentions.users.first();
      let gift = msg.content.split(" ").slice(2)[0]
      if (!person) return msg.reply(`You are incorrectly using the ${data[guildID].prefix}gift command. Please follow it up with a @personToGift and an item.`);
      if (!cash[person.id]) {
          msg.reply(`There is not information about this user in the database.`)
          data[userID] = Object.assign({}, baseCash);
          saveCash();
          return;
      }
      if (gift === "merchant" || gift === "Merchant") {
          if (cash[person.id].moneyMult > 1) return msg.reply(`This user already has the Merchant upgrade.`);
          if (cash[userID].money < 300) return msg.reply(`You do not have enough money to gift this upgrade.`);
          cash[person.id].moneyMult = 2
          saveCash();
          cash[userID].money = cash[userID].money - 300
          saveCash();
          return msg.reply(`You have successfully gifted ${person} the Merchant upgrade!`);
      }
      if (gift === "machine" || gift === "Machine") {
          if (cash[userID].money < 900) return msg.reply(`You do not have enough money to gift this upgrade.`);
          if (cash[person.id].moneyMult < 2) return msg.reply(`This user doesnt have previous upgrades.`);
          if (cash[person.id].moneyMult > 2) return msg.reply(`This user already has the Machine upgrade.`);
          cash[person.id].moneyMult = 4
          saveCash();
          cash[userID].money = cash[userID].money - 900
          saveCash();
          return msg.reply(`You have successfully gifted ${person} the Machine upgrade!`);
      }
      if (gift === "rigged" || gift === "Rigged") {
          if (cash[userID].money < 2500) return msg.reply(`You do not have enough money to gift this upgrade.`);
          if (cash[person.id].moneyMult < 4) return msg.reply(`This user doesnt have previous upgrades.`);
          if (cash[person.id].moneyMult >  4) return msg.reply(`This user already has the rigged upgrade.`)
          cash[person.id].moneyMult = 8;
          saveCash();
          cash[userID].money = cash[userID].money - 2500;
          saveCash();
          return msg.reply(`You have successfully gifted ${person} the rigged upgrade!`);
      }
      if (gift === "fastcharge" || gift === "Fastcharge" || gift === "FastCharge") {
          if (cash[userID].money < 100) return msg.reply(`You do not have enough money to gift this upgrade.`);
          if (cash[person.id].Cooldown < 30000) return msg.reply(`This user already has the FastCharge upgrade.`)
          cash[person.id].Cooldown = 25000
          saveCash();
          cash[userID].money = cash[userID].money - 100
          saveCash();
          return msg.reply(`You have successfully gifted ${person} the FastCharge upgrade!`);
      }
      if (gift === "nitro" || gift === "Nitro") {
          if (cash[userID].money < 300) return msg.reply(`You do not have enough money to gift this upgrade.`);
          if (cash[person.id].Cooldown > 25000) return msg.reply(`This user doesnt have previous upgrades.`);
          if (cash[person.id].Cooldown < 25000) return msg.reply(`This user already has the Nitro upgrade.`);
          cash[person.id].Cooldown = 20000
          saveCash();
          cash[userID].money = cash[userID].money - 100
          saveCash();
          return msg.reply(`You have successfully gifted ${person} the Nitro upgrade!`);
      }
      if (gift === "ftl" || gift === "Ftl" || gift === "FtL" || gift === "FTL") {
          if (cash[userID].money < 1000) return msg.reply(`You do not have enough money to gift this upgrade.`);
          if (cash[person.id].Cooldown > 20000) return msg.reply(`This user doesnt have previous upgrades.`);
          if (cash[person.id].Cooldown < 20000) return msg.reply(`This user already has the FtL upgrade.`)
          cash[person.id].Cooldown = 15000
          saveCash();
          cash[userID].money = cash[userID].money - 1000
          saveCash();
          return msg.reply(`You have successfully gifted ${person} the FtL upgrade!`);
      }
      if (gift === "overcloak" || gift === "Overcloak" || gift === "OverCloak") {
          if (cash[userID].money < 2000) return msg.reply(`You do not have enough money to gift this upgrade.`);
          if (cash[person.id].Cooldown > 15000) return msg.reply(`This user doesnt have previous upgrades.`);
          if (cash[person.id].Cooldown < 15000) return msg.reply(`This user already has the Overcloak upgrade.`)
          cash[person.id].Cooldown = 10000
          saveCash();
          cash[userID].money = cash[userID].money - 2000
          saveCash();
          return msg.reply(`You have successfully gifted ${person} the Overcloak upgrade!`);
      }
      msg.reply(`Please write a name of an upgrade from the shop. Use ${data[guildID].prefix}shop to see whats in the shop.`)
  }

  if (command === "merchant") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if(cash[userID].money < 300) return msg.reply(`You do not have enough money to make this purchase.`);
    if (cash[userID].moneyMult > 1) return msg.reply(`You already bought the "Merchant" upgrade.`);
    if(cash[userID].moneyMult = 2) {
    cash[userID].money = cash[userID].money - 300
    saveCash();
    msg.reply(`You have successfully bought the "Merchant" upgrade! Have fun with that double money upgrade!`)
    }
  }

  if(command === "machine") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if (cash[userID].moneyMult > 2) return msg.reply(`You already bought the "Machine" upgrade.`);
    if(cash[userID].money < 900) return msg.reply(`You do not have enough money to make this purchase.`);
    if (cash[userID].moneyMult !== 2) return msg.reply(`You must buy "Merchant" before buying this upgrade.`)
    if(cash[userID].moneyMult = 4) {
    cash[userID].money = cash[userID].money - 900
    saveCash();
    msg.reply(`You have successfully bought the "Machine" upgrade! Enjoy that massive 4$ per message.`)
    }
  }

  if(command === "rigged") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if (cash[userID].moneyMult === 8) return msg.reply(`You already bought the "Rigged" upgrade.`);
    if(cash[userID].money < 2500) return msg.reply(`You do not have enough money to make this purchase.`);
    if (cash[userID].moneyMult !== 4) return msg.reply(`You must buy pervious upgrades before buying this upgrade.`)
    if(cash[userID].moneyMult = 8) {
    cash[userID].money = cash[userID].money - 2500
    saveCash();
    msg.reply(`You have successfully bought the "Rigged" upgrade! Believe it or not, its actually rigged.`)
    }
  }

  if (command === "fastcharge") {
      if (!msg.content.startsWith(data[guildID].prefix)) return;
      if (cash[userID].Cooldown < 25001) return msg.reply(`You already bought the "Fastcharge" upgrade.`);
      if (cash[userID].money < 100) return msg.reply(`You do not have enough money to make this purchase.`)
      if(cash[userID].Cooldown = 25000) {
      cash[userID].money = cash[userID].money - 100
      saveCash();
      msg.reply(`You have successfully bought the "Fastcharge" upgrade! legit timer got to 25 seconds.`)
      }
  }

  if (command === "nitro") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if (cash[userID].Cooldown < 20001) return msg.reply(`You already bought the "Nitro" upgrade.`);
    if (cash[userID].money < 300) return msg.reply(`You do not have enough money to make this purchase.`)
    if (cash[userID].Cooldown !== 25000) return msg.reply(`You must buy "Fastcharge" before buying this upgrade.`)
    if (cash[userID].Cooldown = 20000) {
        cash[userID].money = cash[userID].money - 300
        saveCash();
        msg.reply(`You have successfully bought the "Nitro" upgrade! 20 seconds aint that much tbh.`)
    }
  }

  if (command === "ftl") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if (cash[userID].Cooldown < 15001) return msg.reply(`You already bought the "Faster Than Light" upgrade.`);
    if (cash[userID].money < 1000) return msg.reply(`You do not have enough money to make this purchase.`)
    if (cash[userID].Cooldown !== 20000) return msg.reply(`You must buy "Fastcharge" and "Nitro" before buying this upgrade.`)
    if (cash[userID].Cooldown = 15000) {
        cash[userID].money = cash[userID].money - 1000
        saveCash();
        msg.reply(`Whoa, 15 seconds! You must be insane going that low.`)
    }
  }

  if (command === "overcloak") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if (cash[userID].Cooldown < 10001) return msg.reply(`You already bought the "overcloak" upgrade.`);
    if (cash[userID].money < 2000) return msg.reply(`You do not have enough money to make this purchase.`)
    if (cash[userID].Cooldown !== 15000) return msg.reply(`You must buy "Fastcharge", "Nitro" and "FTL" before buying this upgrade.`)
    if (cash[userID].Cooldown = 10000) {
        cash[userID].money = cash[userID].money - 2000
        saveCash();
        msg.reply(`Now that's pretty impressive. Have fun with that 10 second delay *cough cough* spam.`)
    }
  }

  if (command === "goodsecurity") {
      if (!msg.content.startsWith(data[guildID].prefix)) return;
      if (cash[userID].money < 200) return msg.reply(`You do not have enough money to make this purchase.`);
      if (cash[userID].bankSecurity > 0) return msg.reply(`You already bought this upgrade.`);
      cash[userID].money = Number(+cash[userID].money - +200);
      cash[userID].bankSecurity = 1
      saveCash();
      msg.reply(`You have successfully bought the "Good Security" upgrade! Robber's chance to succeed is reduced from 30-40% to 30-35%.`);
  }

  if (command === "monkeybank") {
      if (!msg.content.startsWith(data[guildID].prefix)) return;
      if (cash[userID].money < 400) return msg.reply(`You do not have enough money to make this purchase.`);
      if (cash[userID].bankSecurity > 1) return msg.reply(`You already bought this upgrade.`);
      if (cash[userID].bankSecurity < 1) return msg.reply(`You must purchase previous upgrades before purchasing this one`);
      cash[userID].money = Number(+cash[userID].money - +400);
      cash[userID].bankSecurity = 2
      saveCash();
      msg.reply(`You have successfully bought the "Monkey Bank" upgrade! Robber's chance to succeed is reduced from 30-35% to 25-35%`);
  }
  if (command === "bia") {
      if (!msg.content.startsWith(data[guildID].prefix)) return;
      if (cash[userID].money < 750) return msg.reply(`You do not have enough money to make this purchase.`);
      if (cash[userID].bankSecurity > 2) return msg.reply(`You already bought this upgrade.`);
      if (cash[userID].bankSecurity < 2) return msg.reply(`You must purchase previous upgrades before purchasing this one`);
      cash[userID].money = Number(+cash[userID].money - +750);
      cash[userID].bankSecurity = 3
      saveCash();
      msg.reply(`You have successfully bought the "BIA" upgrade! Robber's chance to succeed is reduced from 25-35% to 25-30%`);
  }

  if (command === "security") {
      const person = msg.mentions.users.first();
      if (!person) return msg.reply(`You are incorrectly using the ${data[guildID].prefix}security command. Please follow it up with a @userToCheck his security.`);
      if (!cash[person.id]) {
          msg.reply(`There is not information about this user in the database.`)
          data[userID] = Object.assign({}, baseCash);
          saveCash();
          return;
      }
      if (cash[person.id].bankSecurity === 0) return msg.reply(`This user doesn't have any bank security. Your chance to rob him is 30-40%.`);
      if (cash[person.id].bankSecurity === 1) return msg.reply(`This user has the "Good Security" Security. Your chance to rob him is 30-35%.`);
      if (cash[person.id].bankSecurity === 2) return msg.reply(`This user has the "Monkey Bank" Security. Your chance to rob him is 25-35%.`);
      if (cash[person.id].bankSecurity === 3) return msg.reply(`This user has the "BIA" Security. Your chance to rob him is 25-30%.`);
      msg.reply(`Something went wrong. Please alert Lolization`)
  }

  if (command === "claimdown") {
      if (!cash[userID].claimCooldown) cash[userID].claimCooldown = 86400000
      if (cash[userID].money < 150) return msg.reply(`You do not have enough money to make this purchase.`);
      if (cash[userID].claimCooldown < 86400000) return msg.reply(`You already have this upgrade.`);
      cash[userID].money = Number(+cash[userID].money - +150);
      cash[userID].claimCooldown = 72000000;
      saveCash();
      msg.reply(`You have successfully bought the "Claimdown" upgrade! Claim is reduced from 24 hours to 20 hours.`);
  }

  if (command === "claimer") {
      if (!cash[userID].claimCooldown) cash[userID].claimCooldown = 86400000
      if (cash[userID].claimCooldown > 72000000) return msg.reply(`You must buy previous upgrades before you buy this upgrade.`);
      if (cash[userID].money < 300) return msg.reply(`You do not have enough money to make this purchase.`);
      if (cash[userID].claimCooldown < 72000000) return msg.reply(`You already have this upgrade.`);
      cash[userID].money = Number(+cash[userID].money - +300);
      cash[userID].claimCooldown = 57600000;
      saveCash();
      msg.reply(`You have successfully bought the "Claimer" upgrade! Claim is reduced from 20 hours to 16 hours.`);
  }

  if (command === "claimest") {
      if (!cash[userID].claimCooldown) cash[userID].claimCooldown = 86400000
      if (cash[userID].claimCooldown > 57600000) return msg.reply(`You must buy previous upgrades before you buy this upgrade.`);
      if (cash[userID].money < 600) return msg.reply(`You do not have enough money to make this purchase.`);
      if (cash[userID].claimCooldown < 57600000) return msg.reply(`You already have this upgrade.`);
      cash[userID].money = Number(+cash[userID].money - +600);
      cash[userID].claimCooldown = 43200000;
      saveCash();
      msg.reply(`You have successfully bought the "Claimest" upgrade! Claim is reduced from 16 hours to 12 hours.`);
  }

  if (command === "claimboost") {
      if (!cash[userID].claimBoost) cash[userID].claimBoost = 0
      if (cash[userID].claimBoost > 0) return msg.reply(`You already have this upgrade.`);
      if (cash[userID].money < 70) return msg.reply(`You do not have enough money to make this purchase.`);
      cash[userID].money = Number(+cash[userID].money - +70)
      cash[userID].claimBoost = 10
      saveCash();
      msg.reply(`You have successfuly bought the "Claimboost" upgrade. You now gain +10 more when you claim!`);
  }

  if (command === "claiming") {
      if (!cash[userID].claimBoost) cash[userID].claimBoost = 0
      if (cash[userID].claimBoost > 10) return msg.reply(`You already have this upgrade.`);
      if (cash[userID].claimBoost < 10) return msg.reply(`You must buy previous upgrades before buying this upgrade`);
      if (cash[userID].money < 150) return msg.reply(`You do not have enough money to make this purchase.`);
      cash[userID].money = Number(+cash[userID].money - +150)
      cash[userID].claimBoost = 20
      saveCash();
      msg.reply(`You have successfuly bought the "Claiming" upgrade. You now gain +20 more when you claim!`);
  }

  if (command === "everyday") {
      if (!cash[userID].claimBoost) cash[userID].claimBoost = 0
      if (cash[userID].claimBoost > 20) return msg.reply(`You already have this upgrade.`);
      if (cash[userID].claimBoost < 20) return msg.reply(`You must buy previous upgrades before buying this upgrade`);
      if (cash[userID].money < 200) return msg.reply(`You do not have enough money to make this purchase.`);
      cash[userID].money = Number(+cash[userID].money - +200)
      cash[userID].claimBoost = 30
      saveCash();
      msg.reply(`You have successfuly bought the "Everyday" upgrade. You now gain +30 more when you claim!`);
  }

  if (command === "boosted") {
      if (!cash[userID].claimBoost) cash[userID].claimBoost = 0
      if (cash[userID].claimBoost > 30) return msg.reply(`You already have this upgrade.`);
      if (cash[userID].claimBoost < 30) return msg.reply(`You must buy previous upgrades before buying this upgrade`);
      if (cash[userID].money < 300) return msg.reply(`You do not have enough money to make this purchase.`);
      cash[userID].money = Number(+cash[userID].money - +300)
      cash[userID].claimBoost = 40
      saveCash();
      msg.reply(`You have successfuly bought the "Boosted" upgrade. You now gain +40 more when you claim!`);
  }

  if (command === "maxm8") {
      if (!cash[userID].claimBoost) cash[userID].claimBoost = 0
      if (cash[userID].claimBoost > 40) return msg.reply(`You already have this upgrade.`);
      if (cash[userID].claimBoost < 40) return msg.reply(`You must buy previous upgrades before buying this upgrade`);
      if (cash[userID].money < 400) return msg.reply(`You do not have enough money to make this purchase.`);
      cash[userID].money = Number(+cash[userID].money - +300)
      cash[userID].claimBoost = 50
      saveCash();
      msg.reply(`You have successfuly bought the "MaxM8" upgrade. You now gain +50 more when you claim!`);
  }

  if (command === "rngtbh") {
      if (!cash[userID].claimRng) cash[userID].claimRng = 0
      if (cash[userID].claimRng > 0) return msg.reply(`You already have this upgrade.`);
      if (cash[userID].money < 400) return msg.reply(`You do not have enough money to make this purchase.`);
      cash[userID].money = Number(+cash[userID].money - +400)
      cash[userID].claimRng = 50
      saveCash();
      msg.reply(`You have successfuly bought the "RNGTBH" upgrade. Claim range is now from 1-50 to 1-100`);
  }

  if (command === "rngftw") {
      if (!cash[userID].claimRng) cash[userID].claimRng = 0
      if (cash[userID].claimRng > 50) return msg.reply(`You already have this upgrade.`);
      if (cash[userID].claimRng < 50) return msg.reply(`You must buy previous upgrades before you buy this upgrade.`);
      if (cash[userID].money < 800) return msg.reply(`You do not have enough money to make this purchase.`);
      cash[userID].money = Number(+cash[userID].money - +800)
      cash[userID].claimRng = 150
      saveCash();
      msg.reply(`You have successfuly bought the "RNGFTW" upgrade. Claim range is now from 1-100 to 1-200`);
  }

  if (command === "donate") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    const person = msg.mentions.users.first();
    const amount = msg.content.split(" ").slice(2)[0];
    if (!amount || !person) return msg.reply(`You are incorrectly using the ${data[guildID].prefix}donate command. Please follow it up with a @userToDonate and an amount.`);
    if (person === msg.author) return msg.reply(`You cannot donate to yourself.`)
    if (!cash[person.id]) {
          msg.reply(`There is not information about this user in the database.`)
          data[userID] = Object.assign({}, baseCash);
          saveCash();
          return;
      }
    if (amount > cash[userID].money) return msg.reply(`You cannot donate more than you have.`);
    if (amount < 0) return msg.reply(`You cannot donate negative money.`);
    if (isNaN(amount) || amount === "null") return msg.reply(`Donation amount is by numbers only.`);
    if (amount < 3) return msg.reply(`You must donate at least 3$.`);
    cash[userID].money = Number(cash[userID].money - amount);
    saveCash();
    if (msg.member.roles.exists("name", "Temple of Terror")) cash[person.id].money = Number(+cash[person.id].money + +(+amount * 49/50));
    else if (msg.member.roles.exists("name", "Ground Zero")) cash[person.id].money = Number(+cash[person.id].money + +(+amount * 97/100));
    else if (msg.member.roles.exists("name", "Triple Dart Monkey")) cash[person.id].money = Number(+cash[person.id].money + +(+amount * 96/100));
    else if (msg.member.roles.exists("name", "Bloonjitsu Ninja")) cash[person.id].money = Number(+cash[person.id].money + +(+amount * 95.5/100));
    else cash[person.id].money = Number(+cash[person.id].money + +(+amount * 95/100));
    saveCash();
    if (msg.member.roles.exists("name", "Temple of Terror")) msg.reply(`You have successfully donated ${person} ${amount}$. He has recieved ${amount * 49/50}$. I have taken 2% of the donation.`);
    else if (msg.member.roles.exists("name", "Ground Zero")) msg.reply(`You have successfully donated ${person} ${amount}$. He has recieved ${amount * 97/100}$. I have taken 3% of the donation.`);
    else if (msg.member.roles.exists("name", "Triple Dart Monkey")) msg.reply(`You have successfully donated ${person} ${amount}$. He has recieved ${amount * 96/100}$. I have taken 4% of the donation.`);
    else if (msg.member.roles.exists("name", "Bloonjitsu Ninja")) msg.reply(`You have successfully donated ${person} ${amount}$. He has recieved ${amount * 95.5/100}$. I have taken 4.5% of the donation.`);
    else msg.reply(`You have successfully donated ${person} ${amount}$. He has recieved ${+amount * 95/100}$. I have taken 5% of the donation.`)
  }


  if (command === "stats") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    const time = bot.uptime;
    const seconds = Math.ceil((time/1000)%60);
    const minutes = Math.floor((time/(1000*60))%60);
    const hours = Math.floor((time/(1000*60*60))%24);
    const days = Math.floor((time/(1000*60*60*24)));
    if (minutes < 1 && hours < 1 && days < 1) return msg.channel.sendMessage(`0/0 Dart Bot has been online for ${seconds} seconds.\nThis bot is currently in ${bot.guilds.size} different guilds.\nFor more information about 0/0 Dart Bot, use the ${data[guildID].prefix}help command.`);
    if (minutes === 1 && hours < 1 && days < 1) return msg.channel.sendMessage(`0/0 Dart Bot has been online for one minute and ${seconds} seconds.\nThis bot is currently in ${bot.guilds.size} different guilds.\nFor more information about 0/0 Dart Bot, use the ${data[guildID].prefix}help command.`);
    if (hours < 1 && days < 1) return msg.channel.sendMessage(`0/0 Dart Bot has been online for ${minutes} minutes and ${seconds} seconds.\nThis bot is currently in ${bot.guilds.size} different guilds.\nFor more information about 0/0 Dart Bot, use the ${data[guildID].prefix}help command.`);
    if (hours === 1 && days < 1) return msg.channel.sendMessage(`0/0 Dart Bot has been online for one hour, ${minutes} minutes and ${seconds} seconds.\nThis bot is currently in ${bot.guilds.size} different guilds.\nFor more information about 0/0 Dart Bot, use the ${data[guildID].prefix}help command.`);
    if (days < 1) return msg.channel.sendMessage(`0/0 Dart Bot has been online for ${hours} hours, ${minutes} minutes and ${seconds} seconds.\nThis bot is currently in ${bot.guilds.size} different guilds.\nFor more information about 0/0 Dart Bot, use the ${data[guildID].prefix}help command.`);
    if (days === 1) return msg.channel.sendMessage(`0/0 Dart Bot has been online for one day, ${hours} hours, ${minutes} minutes and ${seconds} seconds.\nThis bot is currently in ${bot.guilds.size} different guilds.\nFor more information about 0/0 Dart Bot, use the ${data[guildID].prefix}help command.`);
    msg.channel.sendMessage(`0/0 Dart Bot has been online for ${days} days, ${hours} hours, ${minutes} minutes and ${seconds} seconds.\nThis bot is currently in ${bot.guilds.size} different guilds.\nFor more information about 0/0 Dart Bot, use the ${data[guildID].prefix}help command.`);
  }

  if (command === "dice") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
      if (msg.channel.id !== '278868948445822976') return msg.delete();
      let random = parseInt(Math.random() * (7 - 1) + 1);
      let roll = msg.content.split(" ").slice(1)[0];
      let amount = msg.content.split(" ").slice(2)[0];
      if (!amount || !roll) return msg.reply(`You are incorrectly using the ${data[guildID].prefix}dice command. Please follow it up with what number to roll and how much.`);
      random = random.toString();
      roll = roll.toString();
      if (roll < 1 || roll > 6) return msg.reply(`Please choose to roll a number from 1 to 6`);
      if (isNaN(amount) || amount === "null") return msg.reply(`Betting amount is by numbers only.`);
      if (amount < 3) return msg.reply(`Smallest bet possible is 3$.`);
      if (cash[userID].money < amount) return msg.reply(`You cannot bet higher than how much you have!`);
      if (roll === random) {
          if (msg.member.roles.exists("name", "Temple of Terror")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "5.7"));
          else if (msg.member.roles.exists("name", "Sun-Terror™")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "5.5"));
          else if (msg.member.roles.exists("name", "Ground Zero")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "5.35"));
          else if (msg.member.roles.exists("name", "Bloon Impact Bomb")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "5.2"));
          else if (msg.member.roles.exists("name", "Triple Dart Monkey")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "5.1"));
          else if (msg.member.roles.exists("name", "Depleted Bloontonium Darts")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "5.0"));
          else if (msg.member.roles.exists("name", "Bloonjitsu Ninja")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "4.9"));
          else if (msg.member.roles.exists("name", "Dart Monkey")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "4.85"));
          else cash[userID].money = parseInt(+cash[userID].money + (+amount * "4.8"));
          saveCash();
          if (msg.member.roles.exists("name", "Temple of Terror")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "5.7"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Sun-Terror™")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "5.5"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Ground Zero")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "5.35"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Bloon Impact Bomb")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "5.2"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Triple Dart Monkey")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "5.1"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Depleted Bloontonium Darts")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "5.0"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Bloonjitsu Ninja")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "4.9"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Dart Monkey")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "4.85"}$! Balance: ${cash[userID].money}$.`);
          else msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "4.8"}$! Balance: ${cash[userID].money}$.`);
          return;
      }
      cash[userID].money = +cash[userID].money - +amount;
      saveCash();
      msg.reply(`You rolled ${random}. You lost ${amount}$. Balance: ${cash[userID].money}$.`);
  }
  if (command === "50x") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
      if (msg.channel.id !== '278868948445822976') return msg.delete();
      let random = parseInt(Math.random() * (101 - 1) + 1);
      let amount = msg.content.split(" ").slice(1);
      if (!amount) return msg.reply(`You are incorrectly using the ${data[guildID].prefix}50x command. Please follow it up with an amount to bet on.`);
      if (cash[userID].money < amount) return msg.reply(`You cannot bet higher than how much you have!`);
      random = random.toString();
      if (amount < 3) return msg.reply(`Smallest bet possible is 3$.`);
      if (isNaN(amount) || amount === "null") return msg.reply(`Betting amount is by numbers only.`);
      if (random > 50) {
          if (msg.member.roles.exists("name", "Temple of Terror")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.6"));
          else if (msg.member.roles.exists("name", "Sun-Terror™")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.4"));
          else if (msg.member.roles.exists("name", "Ground Zero")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.3"));
          else if (msg.member.roles.exists("name", "Bloon Impact Bomb")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.25"));
          else if (msg.member.roles.exists("name", "Triple Dart Monkey")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.2"));
          else if (msg.member.roles.exists("name", "Depleted Bloontonium Darts")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.15"));
          else if (msg.member.roles.exists("name", "Bloonjitsu Ninja")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.1"));
          else if (msg.member.roles.exists("name", "Dart Monkey")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.05"));
          else cash[userID].money = parseInt(+cash[userID].money + +amount);
          saveCash();
          if (msg.member.roles.exists("name", "Temple of Terror")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.6"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Sun-Terror™")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.4"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Ground Zero")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.3"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Bloon Impact Bomb")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.25"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Triple Dart Monkey")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.2"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Depleted Bloontonium Darts")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.15"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Bloonjitsu Ninja")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.1"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Dart Monkey")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.05"}$! Balance: ${cash[userID].money}$.`);
          else msg.reply(`You rolled: ${random}. Nice! You just earned ${amount}$! Balance: ${cash[userID].money}$.`);
          return;
      }
      cash[userID].money = +cash[userID].money - +amount
      saveCash();
      msg.reply(`You rolled: ${random}. You lost ${amount}. Balance: ${cash[userID].money}.`)
  }

  if (command === "give") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    const person = msg.mentions.users.first();
    const amount = msg.content.split(" ").slice(2);
    if (!amount || !person) return msg.reply(`You knew better`);
    if (!cash[person.id]) {
          msg.reply(`There is not information about this user in the database.`)
          data[userID] = Object.assign({}, baseCash);
          saveCash();
          return;
      }
    if (isNaN(amount) || amount === "null") return msg.reply(`Giving amount is by numbers only.`);
    cash[person.id].money = Number(+cash[person.id].money + +amount);
    msg.channel.sendMessage(`k`)
  }

  if (command === "40") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    if (msg.channel.id !== '278868948445822976') return msg.delete();
      let random = parseInt(Math.random() * (101 - 1) + 1);
      let amount = msg.content.split(" ").slice(1);
      if (!amount) return msg.reply(`You are incorrectly using the ${data[guildID].prefix}40 command. Please follow it up with an amount to bet on.`);
      if (cash[userID].money < amount) return msg.reply(`You cannot bet higher than how much you have!`);
      random = random.toString();
      if (amount < 3) return msg.reply(`Smallest bet possible is 3$.`);
      if (isNaN(amount) || amount === "null") return msg.reply(`Betting amount is by numbers only.`);
      if (random > 40) {
          if (msg.member.roles.exists("name", "Temple of Terror")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.5"));
          else if (msg.member.roles.exists("name", "Sun-Terror™")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.35"));
          else if (msg.member.roles.exists("name", "Ground Zero")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.3"));
          else if (msg.member.roles.exists("name", "Bloon Impact Bomb")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.25"));
          else if (msg.member.roles.exists("name", "Triple Dart Monkey")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.2"));
          else if (msg.member.roles.exists("name", "Depleted Bloontonium Darts")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.15"));
          else if (msg.member.roles.exists("name", "Bloonjitsu Ninja")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.1"));
          else if (msg.member.roles.exists("name", "Dart Monkey")) cash[userID].money = parseInt(+cash[userID].money + (+amount * "1.05"));
          else cash[userID].money = parseInt(+cash[userID].money + +amount);
          saveCash();
          if (msg.member.roles.exists("name", "Temple of Terror")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.5"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Sun-Terror™")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.35"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Ground Zero")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.3"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Bloon Impact Bomb")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.25"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Triple Dart Monkey")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.2"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Depleted Bloontonium Darts")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.15"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Bloonjitsu Ninja")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.1"}$! Balance: ${cash[userID].money}$.`);
          else if (msg.member.roles.exists("name", "Dart Monkey")) msg.reply(`You rolled: ${random}. Nice! You just earned ${amount * "1.05"}$! Balance: ${cash[userID].money}$.`);
          else msg.reply(`You rolled: ${random}. Nice! You just earned ${amount}$! Balance: ${cash[userID].money}$.`);
          return;
      }
      cash[userID].money = +cash[userID].money - +amount
      saveCash();
      msg.reply(`You rolled: ${random}. You lost ${amount}. Balance: ${cash[userID].money}.`)
  }



  if (command === "flip") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
      if (msg.channel.id !== '278868948445822976') return msg.delete();
      let random = parseInt(Math.random() * (3 - 1) + 1);
      let roll = msg.content.split(" ").slice(1)[0];
      let amount = msg.content.split(" ").slice(2)[0];
      if (!amount) return msg.reply(`You are incorrectly using the ${data[guildID].prefix}flip command. Please follow it up with heads/tails and an amount to bet on.`);
      if (cash[userID].money < amount) return msg.reply(`You cannot bet higher than how much you have!`);
      if (amount < 3) return msg.reply(`Smallest bet possible is 3$.`);
      if (isNaN(amount) || amount === "null") return msg.reply(`Betting amount is by numbers only.`);
      if (random === 1 && roll === "heads") {
          cash[userID].money = parseInt(+cash[userID].money + +amount);
          saveCash();
          msg.reply(`You flipped: heads. Nice! You just earned ${amount}$! Balance: ${cash[userID].money}$.`);
          return;
      }
      if (random === 2 && roll === "tails") {
          cash[userID].money = parseInt(+cash[userID].money + +amount);
          saveCash();
          msg.reply(`You flipped: tails. Nice! You just earned ${amount}$! Balance: ${cash[userID].money}$.`);
          return;
      }
      if (random === 1 && roll === "tails") {
          cash[userID].money = +cash[userID].money - +amount;
          saveCash();
          msg.reply(`You flipped: heads. You lost ${amount}. Balance: ${cash[userID].money}$.`);
          return;
      }
      if (random === 2 && roll === "heads") {
          cash[userID].money = +cash[userID].money - +amount;
          saveCash();
          msg.reply(`You flipped: tails. You lost ${amount} Balance: ${cash[userID].money}$.`);
          return;
      }
  }

  if (command === "help" || command === "commmands" || command === "cmds") {
    if (!msg.content.startsWith(data[guildID].prefix)) return;
    msg.channel.sendMessage('```**Command list:**\n' + data[guildID].prefix + 'shop: See what you can buy!\n' + data[guildID].prefix + 'dice (number) (amountToBet): Bet on a dice and earn x5.5 if you win!\n' + data[guildID].prefix + '50x (amountToBet): Bet on a number between 1 - 100 and win x2 money if the number is higher than 50!\n' + data[guildID].prefix + 'flip (heads/tails) (amountToBet): flip a coin, and if you flip like your bet you win x2!\n' + data[guildID].prefix + '40 (amountToBet): works like 50x, but with a 60% to win x2.\n' + data[guildID].prefix + 'rob (@userToRob) (amount) : Rob another persons bank with a 30-40% chance. Double money if successful.\n' + data[guildID].prefix + 'buy (stock type) (amount of money): buy a certain stock with money.\n' + data[guildID].prefix + 'sell (stock type) (stock amount): sells a certain amount of stock\n' + data[guildID].prefix + 'values: shows the values of all stocks.```');
  }

  if (msg.content.length > 6) {
    if (msg.channel.id !== "260440225526841354" && msg.channel.id !== "265864809461841920" && msg.channel.id !== "271390861907066880" && msg.channel.id !== "260440362357751808") return;
      if (msg.createdTimestamp - cash[userID].time < cash[userID].Cooldown) return;
        cash[userID].time = msg.createdTimestamp
        cash[userID].money = cash[userID].money + 1 * cash[userID].moneyMult;
        saveCash();
  }

});
bot.on('guildMemberAdd', newMember => {
    const rules = newMember.guild.channels.find("name", "rules")
    const ranks = newMember.guild.channels.find("name", "ranks")
    newMember.guild.defaultChannel.sendMessage(`Welcome ${newMember} to the server! Please go to ${rules} and ${ranks} for more info.`)
});
process.on("unhandledRejection", err => {
  console.error("Uncaught Promise Error:\n" + err.stack)
})
bot.login(config.token);
